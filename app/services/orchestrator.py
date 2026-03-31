from __future__ import annotations

from app.clients.google_places import PlacesProvider
from app.clients.openai_planner import Planner
from app.schemas.chat import ChatRequest, ChatResponse, Ground, RecommendedPlace
from app.schemas.planner import PlannerDecision, SearchRequest


class OrchestratorService:
    def __init__(self, planner: Planner, places_provider: PlacesProvider) -> None:
        self._planner = planner
        self._places_provider = places_provider

    async def handle_chat(self, request: ChatRequest) -> ChatResponse:
        decision = await self._planner.plan(request)

        if decision.intent == "unsupported":
            return ChatResponse(
                status="unsupported",
                intent=decision.intent,
                answer_text=decision.unsupported_reason or "현재 요청은 지원하지 않습니다.",
                grounds=[Ground(source="planner", detail="지원 범위를 벗어난 요청으로 분류했습니다.")],
            )

        if decision.intent == "clarification_needed":
            return ChatResponse(
                status="need_clarification",
                intent=decision.intent,
                answer_text=decision.clarification_question or "조건을 조금 더 알려주세요.",
                follow_up_question=decision.clarification_question,
                grounds=[Ground(source="planner", detail="추천에 필요한 핵심 정보가 부족합니다.")],
            )

        search_query = decision.search_query or request.user_query
        candidates = await self._places_provider.search_places(
            SearchRequest(
                query=search_query,
                destination=decision.destination or request.room_context.destination,
                place_type=decision.place_type,
                max_results=5,
            )
        )

        detailed_candidates = []
        for candidate in candidates[:3]:
            detailed = await self._places_provider.get_place_details(candidate.place_id)
            detailed_candidates.append(detailed or candidate)

        summary = await self._planner.summarize(request, decision, detailed_candidates)
        if not detailed_candidates:
            return ChatResponse(
                status="completed",
                intent=decision.intent,
                answer_text=summary.answer_text,
                follow_up_question="지역이나 카테고리를 더 구체적으로 알려주시면 다시 추천하겠습니다.",
                grounds=[Ground(source="google_places", detail=detail) for detail in summary.grounds],
            )

        recommended_places = [
            RecommendedPlace(
                place_id=candidate.place_id,
                name=candidate.name,
                address=candidate.address,
                lat=candidate.lat,
                lng=candidate.lng,
                primary_type=candidate.primary_type,
                reason=self._build_reason(candidate, decision),
                google_maps_uri=candidate.google_maps_uri,
            )
            for candidate in detailed_candidates
        ]
        grounds = [Ground(source="google_places", detail=detail) for detail in summary.grounds]
        grounds.append(Ground(source="planner", detail="방 컨텍스트와 사용자 질의를 함께 반영했습니다."))
        return ChatResponse(
            status="completed",
            intent=decision.intent,
            answer_text=summary.answer_text,
            recommended_places=recommended_places,
            grounds=grounds,
        )

    @staticmethod
    def _build_reason(candidate: object, decision: PlannerDecision) -> str:
        primary_type = getattr(candidate, "primary_type", None) or "장소"
        address = getattr(candidate, "address", None) or "주소 정보 없음"
        if decision.extracted_preferences:
            return f"{primary_type} 유형이며 {address}에 있습니다. 요청 조건 {', '.join(decision.extracted_preferences)}를 함께 반영했습니다."
        return f"{primary_type} 유형이며 {address}에 있습니다."
