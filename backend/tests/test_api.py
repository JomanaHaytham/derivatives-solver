"""End-to-end API tests, with the AI layer off and with a scripted fake model."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.ai.llm_client import ChatTurn
from app.config import Settings
from app.main import app, chat_service
from app.schemas import ChatRequest
from app.services.chat_service import ChatService

client = TestClient(app)


@pytest.fixture(autouse=True)
def no_ai(monkeypatch):
    monkeypatch.setattr(chat_service, "llm", None)


def post(message, context=None, history=None):
    r = client.post("/api/chat", json={"message": message, "context": context, "history": history or []})
    assert r.status_code == 200
    return r.json()


def test_health():
    assert client.get("/api/health").json()["status"] == "ok"


def test_solution_round_trip():
    r = post("Find the derivative of (x^2 + 1)^5")
    assert r["kind"] == "solution" and r["verified"] is True and r["source"] == "engine"
    assert r["context"]["derivative"] == "10*x*(x**2 + 1)**4"


def test_follow_ups_use_context():
    first = post("Differentiate sin(x^2)")
    why = post("Why did you use the chain rule?", context=first["context"])
    assert why["kind"] == "follow_up" and "chain rule" in why["content"].lower()
    practice = post("Give me a similar problem to practice", context=first["context"])
    assert len(practice["practice"]) == 3
    second = post("Find the second derivative of it", context=first["context"])
    assert second["kind"] == "solution" and second["context"]["order"] == 2


def test_clarification_and_scope():
    assert post("differentiate x^2 +")["kind"] == "clarification"
    assert post("find the second derivative of it")["kind"] == "clarification"   # no context yet
    assert post("integrate x^2")["kind"] == "out_of_scope"
    assert post("differentiate __import__('os')")["kind"] == "clarification"


def test_image_input_not_yet_supported():
    r = client.post("/api/chat", json={"message": "data", "input_type": "image"}).json()
    assert r["kind"] == "error"


def test_validation_rejects_empty_message():
    assert client.post("/api/chat", json={"message": ""}).status_code == 422


# --- AI layer with a scripted fake model -----------------------------------
class FakeLLM:
    name = "fake"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls: list[list[ChatTurn]] = []

    async def complete(self, system, messages, max_tokens=None):
        self.calls.append(messages)
        return self.replies.pop(0)


GOOD = "### Problem\nDifferentiate.\n### Rules we'll use\n- **Chain rule**\n### Step-by-step solution\n**Step 1** ...\nFINAL_ANSWER: 2*x*cos(x^2)"
WRONG = "### Problem\n...\n### Step-by-step solution\n...\nFINAL_ANSWER: cos(x^2)"


def run(service, message, context=None):
    return asyncio.run(service.handle(ChatRequest(message=message, context=context)))


def test_ai_explanation_accepted_when_it_matches():
    fake = FakeLLM([GOOD])
    r = run(ChatService(Settings(), fake), "Differentiate sin(x^2)")
    assert r.source == "ai" and r.verified
    assert "FINAL_ANSWER" not in r.content
    assert "### Final answer" in r.content and "reaches the same answer" in r.content


def test_ai_explanation_corrected_once_then_accepted():
    fake = FakeLLM([WRONG, GOOD])
    r = run(ChatService(Settings(), fake), "Differentiate sin(x^2)")
    assert r.source == "ai" and len(fake.calls) == 2
    assert "not equal to the verified result" in fake.calls[1][-1].content


def test_ai_explanation_discarded_when_still_wrong():
    fake = FakeLLM([WRONG, WRONG])
    r = run(ChatService(Settings(), fake), "Differentiate sin(x^2)")
    assert r.source == "engine"
    assert any("did not match" in w for w in r.warnings)
    assert "2 x \\cos" in r.content  # engine's correct answer is shown


def test_followup_with_wrong_alternative_method_gets_flagged():
    first = run(ChatService(Settings(), None), "Differentiate sin(x^2)")
    fake = FakeLLM(["Another way... FINAL_ANSWER: cos(x^2)\nFINAL_ANSWER: cos(x^2)",
                    "Still...\nFINAL_ANSWER: x*cos(x^2)"])
    r = run(ChatService(Settings(), fake), "Can you solve this using another method?",
            context=first.context)
    assert r.verified is False and "Check failed" in r.content


def test_followup_matching_alternative_method_is_confirmed():
    first = run(ChatService(Settings(), None), "Differentiate sin(x^2)")
    fake = FakeLLM(["Using the limit definition...\nFINAL_ANSWER: 2x cos(x^2)"])
    r = run(ChatService(Settings(), fake), "Can you solve this using another method?", context=first.context)
    assert r.verified is True and "same result" in r.content
