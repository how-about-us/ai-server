from __future__ import annotations

from typing import Sequence

from openai import AsyncOpenAI

from app.schemas.chat import ChatPlanRequest, ChatMessage, StructuredSummary
from app.schemas.planner import ChatAnswerDraft, IntentDecision, PlaceCandidate, PlaceRecommendationDraft


class OpenAITravelClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def summarize_chat(
        self,
        previous_summary: StructuredSummary | None,
        messages: Sequence[ChatMessage],
    ) -> StructuredSummary:
        summary = await self._client.responses.parse(
            model=self._model,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You are a travel chat summarizer for a Korean collaborative travel service. "
                                "Return only structured summary fields. "
                                "Keep only stable facts. Remove small talk, repetition, and filler. "
                                "Preserve decisions, open questions, preferences, constraints, and explicitly mentioned places. "
                                "Write all summary text in Korean."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Update the rolling summary using the previous summary and the new messages.\n"
                                f"previous_summary={self._json(previous_summary.model_dump(mode='json') if previous_summary else None)}\n"
                                f"messages={self._json([message.model_dump(mode='json') for message in messages])}"
                            ),
                        }
                    ],
                },
            ],
            text_format=StructuredSummary,
        )
        return summary.output_parsed

    async def decide_intent(
        self,
        request: ChatPlanRequest,
        updated_summary: StructuredSummary,
    ) -> IntentDecision:
        decision = await self._client.responses.parse(
            model=self._model,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You are an orchestrator for a Korean travel planning service. "
                                "Choose exactly one intent from: place_recommendation, conversation_summary, travel_general_chat, unsupported. "
                                "Use place_recommendation only when the user wants place suggestions. "
                                "Use conversation_summary only when the user wants the chat summarized. "
                                "Use travel_general_chat for travel-planning advice that does not require place search. "
                                "Use unsupported for non-travel topics. "
                                "If place_recommendation is chosen, create a concise Google Places search query in Korean and infer destination if possible."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                f"request_message={self._json(request.request_message.model_dump(mode='json'))}\n"
                                f"room_context={self._json(request.room_context.model_dump(mode='json'))}\n"
                                f"updated_summary={self._json(updated_summary.model_dump(mode='json'))}\n"
                                f"recent_messages={self._json([message.model_dump(mode='json') for message in request.chat_context.recent_messages])}"
                            ),
                        }
                    ],
                },
            ],
            text_format=IntentDecision,
        )
        return decision.output_parsed

    async def compose_place_recommendation(
        self,
        request: ChatPlanRequest,
        updated_summary: StructuredSummary,
        candidates: Sequence[PlaceCandidate],
    ) -> PlaceRecommendationDraft:
        draft = await self._client.responses.parse(
            model=self._model,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You are generating the final Korean response for a travel place recommendation feature. "
                                "Use only the provided summary, request, and place candidate data. "
                                "Do not invent facts beyond the candidate list. "
                                "Return one short answer_text and one reason per place in the same order as the candidates."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                f"request_message={self._json(request.request_message.model_dump(mode='json'))}\n"
                                f"room_context={self._json(request.room_context.model_dump(mode='json'))}\n"
                                f"updated_summary={self._json(updated_summary.model_dump(mode='json'))}\n"
                                f"candidates={self._json([candidate.model_dump(mode='json') for candidate in candidates])}"
                            ),
                        }
                    ],
                },
            ],
            text_format=PlaceRecommendationDraft,
        )
        return draft.output_parsed

    async def compose_chat_answer(
        self,
        request: ChatPlanRequest,
        updated_summary: StructuredSummary,
        intent: str,
    ) -> ChatAnswerDraft:
        draft = await self._client.responses.parse(
            model=self._model,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You are generating a Korean response for a collaborative travel planning service. "
                                "If intent is conversation_summary, summarize the current discussion clearly for humans. "
                                "If intent is travel_general_chat, answer with practical travel-planning advice using only the given context. "
                                "If intent is unsupported, politely refuse and steer back to travel planning."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                f"intent={intent}\n"
                                f"request_message={self._json(request.request_message.model_dump(mode='json'))}\n"
                                f"room_context={self._json(request.room_context.model_dump(mode='json'))}\n"
                                f"updated_summary={self._json(updated_summary.model_dump(mode='json'))}\n"
                                f"recent_messages={self._json([message.model_dump(mode='json') for message in request.chat_context.recent_messages])}"
                            ),
                        }
                    ],
                },
            ],
            text_format=ChatAnswerDraft,
        )
        return draft.output_parsed

    @staticmethod
    def _json(value: object) -> str:
        import json

        return json.dumps(value, ensure_ascii=False)
