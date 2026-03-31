from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ChatStatus = Literal["completed", "need_clarification", "unsupported", "failed"]
Intent = Literal["place_recommendation", "clarification_needed", "unsupported"]


class TravelDateRange(BaseModel):
    start_date: str | None = Field(default=None, examples=["2026-05-04"])
    end_date: str | None = Field(default=None, examples=["2026-05-06"])


class MessageContext(BaseModel):
    role: Literal["user", "assistant", "system"] = "user"
    text: str = Field(..., min_length=1)


class ContextPlace(BaseModel):
    place_id: str | None = None
    name: str
    note: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    primary_type: str | None = None


class RoomContext(BaseModel):
    destination: str | None = Field(default=None, description="여행 지역 또는 중심 지역")
    travel_dates: TravelDateRange | None = None
    participants_count: int | None = Field(default=None, ge=1)
    recent_messages: list[MessageContext] = Field(default_factory=list)
    bookmarked_places: list[ContextPlace] = Field(default_factory=list)
    candidate_places: list[ContextPlace] = Field(default_factory=list)


class ChatRequest(BaseModel):
    user_query: str = Field(..., min_length=1)
    room_context: RoomContext = Field(default_factory=RoomContext)
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "user_query": "도쿄에서 주요 관광지 추천해줘",
                    "room_context": {
                        "destination": "도쿄",
                        "travel_dates": {
                            "start_date": "2026-05-04",
                            "end_date": "2026-05-06",
                        },
                        "participants_count": 3,
                        "recent_messages": [
                            {
                                "role": "user",
                                "text": "우리 도쿄 가서 관광지 위주로 돌자",
                            }
                        ],
                        "bookmarked_places": [],
                        "candidate_places": [],
                    },
                },
                {
                    "user_query": "제주 애월에서 4명이 갈 만한 조용한 카페 추천해줘",
                    "room_context": {
                        "destination": "제주 애월",
                        "travel_dates": {
                            "start_date": "2026-06-12",
                            "end_date": "2026-06-14",
                        },
                        "participants_count": 4,
                        "recent_messages": [
                            {
                                "role": "user",
                                "text": "브런치도 같이 되는 카페면 좋겠어",
                            }
                        ],
                        "bookmarked_places": [
                            {
                                "place_id": "stay-aewol-1",
                                "name": "애월 해안 숙소",
                                "note": "숙소 근처 위주로 찾고 싶음",
                                "address": "제주 제주시 애월읍",
                                "lat": 33.4620,
                                "lng": 126.3100,
                                "primary_type": "lodging",
                            }
                        ],
                        "candidate_places": [],
                    },
                },
            ]
        }
    )


class Ground(BaseModel):
    source: str
    detail: str


class RecommendedPlace(BaseModel):
    place_id: str
    name: str
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    primary_type: str | None = None
    reason: str
    google_maps_uri: str | None = None


class ChatResponse(BaseModel):
    status: ChatStatus
    intent: Intent
    answer_text: str
    follow_up_question: str | None = None
    recommended_places: list[RecommendedPlace] = Field(default_factory=list)
    grounds: list[Ground] = Field(default_factory=list)
