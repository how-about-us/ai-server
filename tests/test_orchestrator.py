from __future__ import annotations

import unittest

from app.clients.google_places import MockGooglePlacesClient
from app.clients.openai_planner import HeuristicPlanner
from app.schemas.chat import ChatRequest, RoomContext
from app.services.orchestrator import OrchestratorService


class OrchestratorServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.service = OrchestratorService(
            planner=HeuristicPlanner(),
            places_provider=MockGooglePlacesClient(),
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

    async def test_returns_recommendations_with_mock_places(self) -> None:
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
