"""FastAPI entry point.

Run with:  uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .ai.llm_client import build_client
from .config import get_settings
from .schemas import ChatRequest, ChatResponse, HealthResponse
from .services.chat_service import ChatService

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

settings = get_settings()
app = FastAPI(title="DeriveIt — AI Derivatives Solver", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

chat_service = ChatService(settings, build_client(settings))


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", ai_enabled=chat_service.llm is not None,
                          model=settings.anthropic_model if chat_service.llm else None)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    try:
        return await chat_service.handle(req)
    except Exception:  # never leak a stack trace to the student
        logging.getLogger(__name__).exception("Unhandled error")
        return ChatResponse(content="Something went wrong on my side while solving that. Please try again, "
                                    "or rephrase the problem.", kind="error", source="engine")


# Serve the built frontend (frontend/dist) when it exists, so one process can run everything.
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        file = (_DIST / path).resolve()
        if path and file.is_file() and _DIST in file.parents:
            return FileResponse(file)
        return FileResponse(_DIST / "index.html")
