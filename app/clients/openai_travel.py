from __future__ import annotations

from typing import Sequence

from openai import AsyncOpenAI

from app.schemas.chat import ChatPlanRequest, ChatMessage, StructuredSummary
from app.schemas.planner import (
    ChatAnswerDraft,
    IntentDecision,
    PlaceCandidate,
    PlaceRerankResult,
    PlaceRecommendationDraft,
)


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
"""
<role>
You are a deterministic summarizer for a Korean collaborative travel planning chat.
</role>

<objective>
Update a rolling structured summary from:
1) previous_summary
2) new messages since last summary
</objective>

<output_contract>
- Return exactly one JSON object that matches the target schema fields.
- Do not include markdown, explanations, or extra keys.
- All natural-language text values must be in Korean.
- If unsure, omit rather than infer.
</output_contract>

<grounding_rules>
- Use only facts supported by the provided input.
- Never invent places, decisions, constraints, or preferences.
- Prefer newer messages when they conflict with previous_summary.
- Keep still-valid facts from previous_summary.
- Remove outdated or contradicted facts.
</grounding_rules>

<recall_priority_rules>
- Prioritize recall for explicit facts in messages.
- If a fact is explicitly stated once and relevant to planning, include it.
- Do not drop explicit constraints/preferences/questions just to be brief.
- Be conservative against invention, but not against extraction.
</recall_priority_rules>

<field_mapping_rules>
- summary_text: 2-4 concise Korean sentences covering current state.
- agreed_points: explicit agreements/decisions only.
- open_questions: unresolved decisions/questions only.
- preferences: expressed likes/dislikes or style preferences.
- constraints: hard limits (budget, time, mobility, headcount, schedule, dietary limits, etc.).
- mentioned_places: explicitly named places only.
- source="chat" for newly mentioned places from messages.
- source="summary" only if retained from previous_summary without new mention.
- source="places" only if the input explicitly marks it as places-derived.
- last_message_id: latest processed message_id if available, else null.
</field_mapping_rules>

<normalization_rules>
- Deduplicate semantically equivalent items.
- Keep list items short, factual, and non-overlapping.
- Exclude chit-chat, jokes, fillers, and repeated paraphrases.
- Do not copy long quotes from messages.
</normalization_rules>

<coverage_checks>
- Before finalizing, verify whether each relevant explicit message has been reflected in at least one field.
- Ensure unresolved decisions are captured in open_questions when no clear agreement exists.
- Ensure stated dislikes/avoidances are captured in preferences or constraints.
- If previous_summary has still-valid open items, retain them unless explicitly resolved.
</coverage_checks>

<length_controls>
- summary_text: max 4 sentences.
- agreed_points/open_questions/preferences/constraints: each max 8 items.
- mentioned_places: max 12 items.
</length_controls>

<done_criteria>
- Output is schema-compatible.
- No unsupported claims.
- Reflects latest state of discussion.
</done_criteria>
"""
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
                                """
You are an orchestrator for a Korean travel planning service. 
Choose exactly one intent from: place_recommendation, conversation_summary, travel_general_chat, unsupported.
- Use place_recommendation only when the user wants place suggestions. 
- Use conversation_summary only when the user wants the chat summarized. 
- Use travel_general_chat for travel-planning advice that does not require place search. 
- Use unsupported for non-travel topics. 

If place_recommendation is chosen, create a concise Google Places search query in Korean and infer destination if possible.
                                """
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

    async def rerank_place_candidates(
        self,
        request: ChatPlanRequest,
        updated_summary: StructuredSummary,
        candidates: Sequence[PlaceCandidate],
    ) -> PlaceRerankResult:
        rerank = await self._client.responses.parse(
            model=self._model,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You are a travel place ranking assistant for a Korean travel planning service. "
                                "Rank place candidates based on the user request, chat context, and reviews. "
                                "Use only provided candidate/review data. Do not invent facts. "
                                "Prefer places that best match explicit user constraints and preferences. "
                                "Penalize candidates with weak or conflicting review evidence. "
                                "Return up to 3 place_ids in ranked order, and a scored list for all candidates."
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
            text_format=PlaceRerankResult,
        )
        return rerank.output_parsed

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
