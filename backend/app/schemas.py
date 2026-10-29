"""Request / response models for the HTTP API."""

from __future__ import annotations

from typing import Any, Literal

try:
    from pydantic import BaseModel, Field
except ImportError:  # in-browser build (Pyodide) ships without pydantic
    from ._lite_models import BaseModel, Field


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=20000)


class SolutionContext(BaseModel):
    """Summary of the last solved problem; returned by the server, echoed back by the client."""
    original: str
    original_latex: str = ""
    variable: str = "x"
    order: int = 1
    implicit: bool = False
    derivative: str
    derivative_latex: str = ""
    answer_latex: str = ""
    rules: list[str] = []
    verified: bool = False
    verification_method: str = ""


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    input_type: Literal["text", "image"] = "text"
    history: list[HistoryMessage] = []
    context: SolutionContext | None = None


MessageKind = Literal["solution", "follow_up", "clarification", "out_of_scope", "error"]


class ChatResponse(BaseModel):
    content: str                       # Markdown with $...$ / $$...$$ math
    kind: MessageKind
    source: Literal["ai", "engine"]    # who wrote the explanation text
    verified: bool | None = None       # engine verification of the derivative, if any
    context: SolutionContext | None = None
    warnings: list[str] = []
    practice: list[str] = []           # plain-text practice problems the UI can offer as buttons


class HealthResponse(BaseModel):
    status: str
    ai_enabled: bool
    model: str | None
    details: dict[str, Any] = {}
