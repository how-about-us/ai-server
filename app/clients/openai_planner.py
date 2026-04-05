from __future__ import annotations

import json
from typing import Protocol

from openai import AsyncOpenAI
from pydantic import ValidationError

from app.schemas.chat import ChatRequest
from app.schemas.planner import PlaceCandidate, PlannerDecision, SummaryPayload


class Planner(Protocol):
    async def plan(self, request: ChatRequest) -> PlannerDecision:
        ...

    async def summarize(
        self,
        request: ChatRequest,
        decision: PlannerDecision,
        candidates: list[PlaceCandidate],
    ) -> SummaryPayload:
        ...


class OpenAIPlanner:
    _UNSUPPORTED_KEYWORDS = ("항공권", "예약", "결제", "비행기", "숙소 예약")
    _CAFE_KEYWORDS = ("카페", "커피", "디저트", "브런치")
    _RESTAURANT_KEYWORDS = ("식당", "맛집", "점심", "저녁", "브런치", "밥")
    _ATTRACTION_KEYWORDS = ("관광", "산책", "볼거리", "가볼만", "명소")
    _INTENT_ALIASES = {
        "place_recommendation": "place_recommendation",
        "recommendation": "place_recommendation",
        "place": "place_recommendation",
        "places": "place_recommendation",
        "category": "place_recommendation",
        "clarification_needed": "clarification_needed",
        "need_clarification": "clarification_needed",
        "clarification": "clarification_needed",
        "unsupported": "unsupported",
    }

    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def plan(self, request: ChatRequest) -> PlannerDecision:
        system_prompt = (
            "너는 여행 계획 서비스의 장소 추천 플래너다. "
            "사용자 질의를 다음 중 하나로만 분류하라: "
            "place_recommendation, clarification_needed, unsupported. "
            "예약, 결제, 항공권, 숙소 예약, 직접 상태 변경 요청은 unsupported로 처리하라. "
            "지역 정보가 없으면 clarification_needed로 처리하라. "
            "반드시 JSON object만 반환하라."
        )
        user_prompt = json.dumps(
            {
                "user_query": request.user_query,
                "room_context": request.room_context.model_dump(mode="json"),
            },
            ensure_ascii=False,
        )
        completion = await self._client.chat.completions.create(
            model=self._model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = completion.choices[0].message.content or "{}"
        try:
            data = json.loads(content)
            normalized = self._normalize_planner_payload(data, request)
            return PlannerDecision.model_validate(normalized)
        except (json.JSONDecodeError, TypeError, ValidationError):
            return self._build_fallback_decision(request)

    async def summarize(
        self,
        request: ChatRequest,
        decision: PlannerDecision,
        candidates: list[PlaceCandidate],
    ) -> SummaryPayload:
        system_prompt = (
            "너는 여행 장소 추천 응답을 생성하는 어시스턴트다. "
            "툴 결과에 없는 사실은 추정하지 말고, 추천 이유는 짧고 구체적으로 써라. "
            "반드시 JSON object만 반환하라."
        )
        user_prompt = json.dumps(
            {
                "user_query": request.user_query,
                "decision": decision.model_dump(mode="json"),
                "candidates": [candidate.model_dump(mode="json") for candidate in candidates[:5]],
            },
            ensure_ascii=False,
        )
        completion = await self._client.chat.completions.create(
            model=self._model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = completion.choices[0].message.content or "{}"
        try:
            data = json.loads(content)
            return SummaryPayload.model_validate(data)
        except (json.JSONDecodeError, TypeError, ValidationError):
            return self._build_fallback_summary(request, decision, candidates)

    def _normalize_planner_payload(self, data: object, request: ChatRequest) -> dict[str, object]:
        if not isinstance(data, dict):
            raise TypeError("Planner response must be a JSON object.")

        normalized = dict(data)
        raw_intent = normalized.get("intent") or normalized.get("category")
        mapped_intent = None
        if isinstance(raw_intent, str):
            mapped_intent = self._INTENT_ALIASES.get(raw_intent.strip().lower())
        if mapped_intent:
            normalized["intent"] = mapped_intent

        destination = normalized.get("destination") or request.room_context.destination
        party_size = normalized.get("party_size") or request.room_context.participants_count
        user_query = request.user_query.strip()

        if not normalized.get("intent"):
            raise TypeError("Planner response is missing intent.")

        if destination:
            normalized["destination"] = destination
        if party_size is not None:
            normalized["party_size"] = party_size

        if normalized["intent"] == "place_recommendation":
            if not destination:
                normalized["intent"] = "clarification_needed"
                normalized.setdefault("clarification_question", "어느 지역을 기준으로 추천할지 알려주세요.")
                normalized.pop("search_query", None)
            else:
                normalized.setdefault("search_query", f"{destination} {user_query}".strip())
                normalized.setdefault("place_type", self._infer_place_type(user_query.lower()))
                if not normalized.get("extracted_preferences"):
                    normalized["extracted_preferences"] = self._extract_preferences(user_query)

        if normalized["intent"] == "clarification_needed":
            normalized.setdefault("clarification_question", "어느 지역을 기준으로 추천할지 알려주세요.")

        if normalized["intent"] == "unsupported":
            normalized.setdefault(
                "unsupported_reason",
                "현재는 여행 장소 추천만 지원하고 예약이나 결제는 지원하지 않습니다.",
            )

        return normalized

    def _build_fallback_decision(self, request: ChatRequest) -> PlannerDecision:
        query = request.user_query.strip()
        lowered = query.lower()
        destination = request.room_context.destination
        party_size = request.room_context.participants_count

        if any(keyword in query for keyword in self._UNSUPPORTED_KEYWORDS):
            return PlannerDecision(
                intent="unsupported",
                unsupported_reason="현재는 여행 장소 추천만 지원하고 예약이나 결제는 지원하지 않습니다.",
                party_size=party_size,
                destination=destination,
            )

        if not destination:
            return PlannerDecision(
                intent="clarification_needed",
                clarification_question="어느 지역을 기준으로 추천할지 알려주세요.",
                party_size=party_size,
            )

        return PlannerDecision(
            intent="place_recommendation",
            search_query=f"{destination} {query}".strip(),
            place_type=self._infer_place_type(lowered),
            extracted_preferences=self._extract_preferences(query),
            party_size=party_size,
            destination=destination,
        )

    def _build_fallback_summary(
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

        top_candidates = candidates[:3]
        lines = [f"{request.room_context.destination or '해당 지역'} 기준으로 추천할 만한 장소입니다."]
        grounds: list[str] = []
        for candidate in top_candidates:
            reason = self._reason_for_candidate(candidate, decision)
            lines.append(f"- {candidate.name}: {reason}")
            grounds.append(f"{candidate.name} 검색 결과를 기반으로 추천했습니다.")
        return SummaryPayload(answer_text="\n".join(lines), grounds=grounds)

    def _infer_place_type(self, lowered_query: str) -> str | None:
        if any(token in lowered_query for token in self._CAFE_KEYWORDS):
            return "cafe"
        if any(token in lowered_query for token in self._RESTAURANT_KEYWORDS):
            return "restaurant"
        if any(token in lowered_query for token in self._ATTRACTION_KEYWORDS):
            return "tourist_attraction"
        return None

    @staticmethod
    def _extract_preferences(query: str) -> list[str]:
        tokens = []
        for keyword in ("조용", "오션뷰", "바다", "브런치", "4명", "단체", "저녁"):
            if keyword in query:
                tokens.append(keyword)
        return tokens

    @staticmethod
    def _reason_for_candidate(candidate: PlaceCandidate, decision: PlannerDecision) -> str:
        preference_text = ""
        if decision.extracted_preferences:
            preference_text = f" 요청한 조건({', '.join(decision.extracted_preferences)})을 함께 고려했습니다."
        type_text = candidate.primary_type or "장소"
        return f"{type_text} 유형으로 검색되었고 주소는 {candidate.address or '미상'}입니다.{preference_text}"
