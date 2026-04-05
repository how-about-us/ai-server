from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException

from app.dependencies import get_logger, get_orchestrator_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.orchestrator import OrchestratorService


app = FastAPI(
    title="Travel AI Server",
    version="0.1.0",
    description="FastAPI AI backend for collaborative travel place recommendations",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/ai/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    service: OrchestratorService = Depends(get_orchestrator_service),
) -> ChatResponse:
    logger = get_logger()
    try:
        return await service.handle_chat(request)
    except Exception as exc:  # pragma: no cover
        logger.exception("AI chat request failed")
        raise HTTPException(status_code=500, detail="AI request failed") from exc
