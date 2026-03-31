from __future__ import annotations

import os
import unittest

import httpx

from app.dependencies import reset_cached_dependencies
from app.main import app


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        os.environ["AI_USE_MOCK_SERVICES"] = "true"
        reset_cached_dependencies()
        transport = httpx.ASGITransport(app=app)
        self.client = httpx.AsyncClient(transport=transport, base_url="http://testserver")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        os.environ.pop("AI_USE_MOCK_SERVICES", None)
        reset_cached_dependencies()

    async def test_health(self) -> None:
        response = await self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    async def test_chat_endpoint_returns_mock_recommendations(self) -> None:
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
