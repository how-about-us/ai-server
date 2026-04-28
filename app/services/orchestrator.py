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
        # Fetch details for all 5 candidates first (review-aware if supported by the provider),
        # then let the LLM rerank to pick Top 3.
        detailed_candidates: list[PlaceCandidate] = []
        for candidate in candidates[:5]:
            detailed: PlaceCandidate | None = None
            get_with_reviews = getattr(self.places_provider, "get_place_details_with_reviews", None)
            if callable(get_with_reviews):
                detailed = await get_with_reviews(candidate.place_id, review_limit=5)
            if detailed is None:
                detailed = await self.places_provider.get_place_details(candidate.place_id)
            detailed_candidates.append(detailed or candidate)

        # LLM rerank: if it fails or returns empty, fall back to the first 3 detailed candidates.
        reranked_candidates: list[PlaceCandidate] = []
        try:
            rerank = await self.ai_client.rerank_place_candidates(
                request=request,
                updated_summary=updated_summary,
                candidates=detailed_candidates,
            )
            id_to_candidate = {c.place_id: c for c in detailed_candidates}
            for place_id in rerank.top_place_ids:
                if place_id in id_to_candidate:
                    reranked_candidates.append(id_to_candidate[place_id])
        except Exception:  # pragma: no cover
            reranked_candidates = []

        selected_candidates = reranked_candidates[:3] if reranked_candidates else detailed_candidates[:3]

        if not selected_candidates:
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

        # Don't feed long reviews into final answer generation (token control).
        candidates_for_answer = [c.model_copy(update={"reviews": []}) for c in selected_candidates]
        draft = await self.ai_client.compose_place_recommendation(
            request,
            updated_summary,
            candidates_for_answer,
        )
        reasons = draft.place_reasons[: len(candidates_for_answer)]
        while len(reasons) < len(candidates_for_answer):
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
            for index, candidate in enumerate(selected_candidates)
        ]
        return ChatPlanResponse(
            intent="place_recommendation",
            answer_text=draft.answer_text,
            recommended_places=recommended_places,
            updated_summary=updated_summary,
        )
