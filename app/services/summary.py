from __future__ import annotations

from dataclasses import dataclass

from app.clients.openai_travel import OpenAITravelClient
from app.schemas.chat import ChatMessage, StructuredSummary, SummaryUpdateRequest, SummaryUpdateResponse


@dataclass(slots=True)
class SummaryService:
    ai_client: OpenAITravelClient

    async def merge_summary(
        self,
        previous_summary: StructuredSummary | None,
        messages: list[ChatMessage],
    ) -> StructuredSummary:
        return await self.ai_client.summarize_chat(
            previous_summary=previous_summary,
            messages=messages,
        )

    async def create_summary(self, request: SummaryUpdateRequest) -> SummaryUpdateResponse:
        summary = await self.merge_summary(
            previous_summary=request.previous_summary,
            messages=request.messages_since_last_summary,
        )
        return SummaryUpdateResponse(room_id=request.room_id, summary=summary)
