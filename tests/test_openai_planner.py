from __future__ import annotations

import json
import unittest

from app.clients.openai_planner import OpenAIPlanner
from app.schemas.chat import ChatRequest, RoomContext


class _FakeCompletions:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses

    async def create(self, **_: object) -> object:
        content = self._responses.pop(0)
        message = type("Message", (), {"content": content})()
        choice = type("Choice", (), {"message": message})()
        return type("Completion", (), {"choices": [choice]})()


class _FakeChat:
    def __init__(self, responses: list[str]) -> None:
        self.completions = _FakeCompletions(responses)


class _FakeClient:
    def __init__(self, responses: list[str]) -> None:
        self.chat = _FakeChat(responses)


class OpenAIPlannerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.planner = OpenAIPlanner(api_key="test-key", model="test-model")

    async def test_plan_accepts_category_alias_and_backfills_fields(self) -> None:
        self.planner._client = _FakeClient([json.dumps({"category": "place_recommendation"})])

        decision = await self.planner.plan(
            ChatRequest(
                user_query="조용한 카페 추천해줘",
                room_context=RoomContext(destination="제주 애월", participants_count=4),
            )
        )

        self.assertEqual(decision.intent, "place_recommendation")
        self.assertEqual(decision.destination, "제주 애월")
        self.assertEqual(decision.party_size, 4)
        self.assertEqual(decision.place_type, "cafe")
        self.assertIn("제주 애월", decision.search_query or "")
        self.assertIn("조용", decision.extracted_preferences)

    async def test_plan_uses_internal_fallback_when_response_is_invalid(self) -> None:
        self.planner._client = _FakeClient([json.dumps({"foo": "bar"})])

        decision = await self.planner.plan(
            ChatRequest(
                user_query="제주 애월 카페 추천해줘",
                room_context=RoomContext(destination="제주 애월", participants_count=2),
            )
        )

        self.assertEqual(decision.intent, "place_recommendation")
        self.assertEqual(decision.destination, "제주 애월")
        self.assertEqual(decision.party_size, 2)
        self.assertEqual(decision.place_type, "cafe")

    async def test_summarize_uses_internal_fallback_when_response_is_invalid(self) -> None:
        self.planner._client = _FakeClient([json.dumps({"oops": "invalid"})])
        request = ChatRequest(
            user_query="제주 애월 카페 추천해줘",
            room_context=RoomContext(destination="제주 애월"),
        )
        decision = await self.planner.plan(request)

        self.planner._client = _FakeClient([json.dumps({"not_answer_text": "missing"})])
        summary = await self.planner.summarize(request, decision, [])

        self.assertIn("조건에 맞는 장소를 바로 찾지 못했습니다", summary.answer_text)
        self.assertGreaterEqual(len(summary.grounds), 1)
