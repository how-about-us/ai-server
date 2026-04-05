from __future__ import annotations

import unittest

from app.schemas.chat import ChatRequest, RoomContext
from app.schemas.planner import PlaceCandidate, PlannerDecision, SearchRequest, SummaryPayload
from app.services.orchestrator import OrchestratorService


class _FakePlanner:
    async def plan(self, request: ChatRequest) -> PlannerDecision:
        query = request.user_query.strip()
        destination = request.room_context.destination

        if "항공권" in query:
            return PlannerDecision(
                intent="unsupported",
                unsupported_reason="현재는 여행 장소 추천만 지원하고 예약이나 결제는 지원하지 않습니다.",
                destination=destination,
            )

        if not destination:
            return PlannerDecision(
                intent="clarification_needed",
                clarification_question="어느 지역을 기준으로 추천할지 알려주세요.",
            )

        return PlannerDecision(
            intent="place_recommendation",
            search_query=f"{destination} {query}",
            place_type="cafe" if "카페" in query else None,
            extracted_preferences=["조용"] if "조용" in query else [],
            party_size=request.room_context.participants_count,
            destination=destination,
        )

    async def summarize(
        self,
        request: ChatRequest,
        decision: PlannerDecision,
        candidates: list[PlaceCandidate],
    ) -> SummaryPayload:
        if not candidates:
            return SummaryPayload(
                answer_text="조건에 맞는 장소를 바로 찾지 못했습니다. 지역이나 카테고리를 더 구체적으로 알려주시면 다시 추천하겠습니다.",
                grounds=["Google Places 검색 결과가 비어 있었습니다."],
            )
        return SummaryPayload(
            answer_text=f"{request.room_context.destination} 기준 추천 결과입니다.",
            grounds=[f"{candidate.name} 검색 결과를 기반으로 추천했습니다." for candidate in candidates],
        )


class _FakePlacesProvider:
    def __init__(self) -> None:
        self._candidates = [
            PlaceCandidate(
                place_id="place-1",
                name="애월 바다정원",
                address="제주 제주시 애월읍 애월해안로 100",
                lat=33.4610,
                lng=126.3090,
                primary_type="cafe",
                google_maps_uri="https://maps.example.com/place-1",
            ),
            PlaceCandidate(
                place_id="place-2",
                name="하늘카페 애월",
                address="제주 제주시 애월읍 곽지길 21",
                lat=33.4504,
                lng=126.3059,
                primary_type="cafe",
                google_maps_uri="https://maps.example.com/place-2",
            ),
        ]

    async def search_places(self, request: SearchRequest) -> list[PlaceCandidate]:
        if request.destination == "제주 애월":
            return self._candidates[: request.max_results]
        return []

    async def get_place_details(self, place_id: str) -> PlaceCandidate | None:
        for candidate in self._candidates:
            if candidate.place_id == place_id:
                return candidate
        return None


class OrchestratorServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.service = OrchestratorService(
            planner=_FakePlanner(),
            places_provider=_FakePlacesProvider(),
        )

    async def test_returns_clarification_when_destination_missing(self) -> None:
        response = await self.service.handle_chat(
            ChatRequest(
                user_query="카페 추천해줘",
                room_context=RoomContext(destination=None),
            )
        )

        self.assertEqual(response.status, "need_clarification")
        self.assertEqual(response.intent, "clarification_needed")
        self.assertTrue(response.follow_up_question)

    async def test_returns_unsupported_for_booking_request(self) -> None:
        response = await self.service.handle_chat(
            ChatRequest(
                user_query="제주 항공권 예약해줘",
                room_context=RoomContext(destination="제주 애월"),
            )
        )

        self.assertEqual(response.status, "unsupported")
        self.assertEqual(response.intent, "unsupported")

    async def test_returns_recommendations_with_fake_places(self) -> None:
        response = await self.service.handle_chat(
            ChatRequest(
                user_query="카페 추천해줘",
                room_context=RoomContext(destination="제주 애월", participants_count=4),
            )
        )

        self.assertEqual(response.status, "completed")
        self.assertEqual(response.intent, "place_recommendation")
        self.assertGreaterEqual(len(response.recommended_places), 1)
        self.assertIn("애월", response.answer_text)
