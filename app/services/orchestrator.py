from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.clients.openai_travel import OpenAITravelClient
from app.schemas.chat import ChatPlanRequest, ChatPlanResponse, RecommendedPlace, StructuredSummary
from app.schemas.planner import IntentDecision, PlaceCandidate, SearchRequest
from app.services.summary import SummaryService


class PlacesProvider(Protocol):
    async def search_places(self, request: SearchRequest) -> list[PlaceCandidate]:
        ...

    async def get_place_details(self, place_id: str) -> PlaceCandidate | None:
        ...


@dataclass(slots=True)
class ChatPlanService:
    summary_service: SummaryService
    ai_client: OpenAITravelClient
    places_provider: PlacesProvider

    async def handle(self, request: ChatPlanRequest) -> ChatPlanResponse:
        updated_summary = (
            await self.summary_service.merge_summary(
                previous_summary=request.chat_context.summary,
                messages=request.chat_context.messages_since_last_summary,
            )
            if request.chat_context.messages_since_last_summary
            else request.chat_context.summary or StructuredSummary()
        )

        decision = await self.ai_client.decide_intent(request, updated_summary)
        if decision.intent == "place_recommendation":
            return await self._handle_place_recommendation(request, decision, updated_summary)

        answer = await self.ai_client.compose_chat_answer(
            request,
            updated_summary,
            decision.intent,
        )
        return ChatPlanResponse(
            intent=decision.intent,
            answer_text=answer.answer_text,
            updated_summary=updated_summary,
        )

    async def _handle_place_recommendation(
        self,
        request: ChatPlanRequest,
        decision: IntentDecision,
        updated_summary: StructuredSummary,
    ) -> ChatPlanResponse:
        destination = decision.destination or request.room_context.destination
        if not destination:
            answer = await self.ai_client.compose_chat_answer(
                request,
                updated_summary,
                "travel_general_chat",
            )
            return ChatPlanResponse(
                intent="place_recommendation",
                answer_text=answer.answer_text,
                updated_summary=updated_summary,
            )

        candidates = await self.places_provider.search_places(
            SearchRequest(
                query=decision.search_query or destination,
                destination=destination,
                place_type=decision.place_type,
                max_results=5,
            )
        )
        detailed_candidates: list[PlaceCandidate] = []
        for candidate in candidates[:3]:
            detailed = await self.places_provider.get_place_details(candidate.place_id)
            detailed_candidates.append(detailed or candidate)

        if not detailed_candidates:
            answer = await self.ai_client.compose_chat_answer(
                request,
                updated_summary,
                "travel_general_chat",
            )
            return ChatPlanResponse(
                intent="place_recommendation",
                answer_text=answer.answer_text,
                updated_summary=updated_summary,
            )

        draft = await self.ai_client.compose_place_recommendation(
            request,
            updated_summary,
            detailed_candidates,
        )
        reasons = draft.place_reasons[: len(detailed_candidates)]
        while len(reasons) < len(detailed_candidates):
            reasons.append("요청한 여행 맥락을 반영해 추천한 후보입니다.")

        recommended_places = [
            RecommendedPlace(
                place_id=candidate.place_id,
                name=candidate.name,
                address=candidate.address,
                lat=candidate.lat,
                lng=candidate.lng,
                primary_type=candidate.primary_type,
                google_maps_uri=candidate.google_maps_uri,
                reason=reasons[index],
            )
            for index, candidate in enumerate(detailed_candidates)
        ]
        return ChatPlanResponse(
            intent="place_recommendation",
            answer_text=draft.answer_text,
            recommended_places=recommended_places,
            updated_summary=updated_summary,
        )
