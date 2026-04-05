from __future__ import annotations

import unittest

import httpx

from app.dependencies import get_orchestrator_service
from app.main import app
from app.schemas.chat import ChatRequest, RoomContext
from app.schemas.planner import PlaceCandidate, PlannerDecision, SearchRequest, SummaryPayload
from app.services.orchestrator import OrchestratorService


class _FakePlanner:
    async def plan(self, request: ChatRequest) -> PlannerDecision:
        destination = request.room_context.destination
        if not destination:
            return PlannerDecision(
                intent="clarification_needed",
                clarification_question="어느 지역을 기준으로 추천할지 알려주세요.",
            )
        return PlannerDecision(
            intent="place_recommendation",
            search_query=f"{destination} {request.user_query}",
            place_type="cafe",
            destination=destination,
            party_size=request.room_context.participants_count,
        )

    async def summarize(
        self,
        request: ChatRequest,
        decision: PlannerDecision,
        candidates: list[PlaceCandidate],
    ) -> SummaryPayload:
        return SummaryPayload(
            answer_text=f"{request.room_context.destination} 기준 추천 결과입니다.",
            grounds=[f"{candidate.name} 검색 결과를 기반으로 추천했습니다." for candidate in candidates],
        )


class _FakePlacesProvider:
    def __init__(self) -> None:
        self._candidate = PlaceCandidate(
            place_id="place-1",
            name="애월 바다정원",
            address="제주 제주시 애월읍 애월해안로 100",
            lat=33.4610,
            lng=126.3090,
            primary_type="cafe",
            google_maps_uri="https://maps.example.com/place-1",
        )

    async def search_places(self, request: SearchRequest) -> list[PlaceCandidate]:
        return [self._candidate]

    async def get_place_details(self, place_id: str) -> PlaceCandidate | None:
        if place_id == self._candidate.place_id:
            return self._candidate
        return None


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        app.dependency_overrides[get_orchestrator_service] = lambda: OrchestratorService(
            planner=_FakePlanner(),
            places_provider=_FakePlacesProvider(),
        )
        transport = httpx.ASGITransport(app=app)
        self.client = httpx.AsyncClient(transport=transport, base_url="http://testserver")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()

    async def test_health(self) -> None:
        response = await self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    async def test_chat_endpoint_returns_recommendations(self) -> None:
        response = await self.client.post(
            "/v1/ai/chat",
            json={
                "user_query": "제주 애월 카페 추천해줘",
                "room_context": {
                    "destination": "제주 애월",
                    "participants_count": 2,
                    "recent_messages": [],
                    "bookmarked_places": [],
                    "candidate_places": [],
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["intent"], "place_recommendation")
        self.assertGreaterEqual(len(body["recommended_places"]), 1)
