from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException

from app.dependencies import get_chat_plan_service, get_logger, get_summary_service
from app.schemas.chat import (
    ChatPlanRequest,
    ChatPlanResponse,
    SummaryUpdateRequest,
    SummaryUpdateResponse,
)
from app.services.orchestrator import ChatPlanService
from app.services.summary import SummaryService


app = FastAPI(
    title="Travel AI Server",
    version="0.2.0",
    description="Stateless FastAPI AI backend for travel chat summarization and planning",
)


@app.post("/v1/ai/context/summaries", response_model=SummaryUpdateResponse)
async def update_summary(
    request: SummaryUpdateRequest,
    service: SummaryService = Depends(get_summary_service),
) -> SummaryUpdateResponse:
    logger = get_logger()
    try:
        return await service.create_summary(request)
    except Exception as exc:  # pragma: no cover
        logger.exception("Summary update request failed")
        raise HTTPException(status_code=500, detail="Summary update failed") from exc


@app.post("/v1/ai/chat/plan", response_model=ChatPlanResponse)
async def chat_plan(
    request: ChatPlanRequest,
    service: ChatPlanService = Depends(get_chat_plan_service),
) -> ChatPlanResponse:
    logger = get_logger()
    try:
        return await service.handle(request)
    except Exception as exc:  # pragma: no cover
        logger.exception("Chat plan request failed")
        raise HTTPException(status_code=500, detail="Chat plan failed") from exc
