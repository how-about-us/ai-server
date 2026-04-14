from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Intent = Literal[
    "place_recommendation",
    "conversation_summary",
    "travel_general_chat",
    "unsupported",
]


class TravelDateRange(BaseModel):
    start_date: str | None = Field(default=None, examples=["2026-05-03"])
    end_date: str | None = Field(default=None, examples=["2026-05-05"])


class MentionedPlace(BaseModel):
    name: str
    source: Literal["chat", "summary", "places"] = "chat"
    note: str | None = None


class StructuredSummary(BaseModel):
    summary_text: str = ""
    agreed_points: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    mentioned_places: list[MentionedPlace] = Field(default_factory=list)
    last_message_id: str | None = None


class ChatMessage(BaseModel):
    message_id: str = Field(..., min_length=1)
    sender_id: str | None = None
    sender_name: str = Field(..., min_length=1)
    sent_at: str | None = None
    text: str = Field(..., min_length=1)


class ContextPlace(BaseModel):
    place_id: str | None = None
    name: str
    note: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    primary_type: str | None = None
    google_maps_uri: str | None = None


class RoomContext(BaseModel):
    destination: str | None = Field(default=None, description="여행 지역 또는 중심 지역")
    travel_dates: TravelDateRange | None = None
    participants_count: int | None = Field(default=None, ge=1)
    bookmarked_places: list[ContextPlace] = Field(default_factory=list)
    candidate_places: list[ContextPlace] = Field(default_factory=list)


class SummaryUpdateRequest(BaseModel):
    team_id: str = Field(..., min_length=1)
    room_id: str = Field(..., min_length=1)
    messages_since_last_summary: list[ChatMessage] = Field(..., min_length=1)
    previous_summary: StructuredSummary | None = None
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "team_id": "team_123",
                    "room_id": "room_456",
                    "messages_since_last_summary": [
                        {
                            "message_id": "msg_101",
                            "sender_id": "user_1",
                            "sender_name": "민수",
                            "sent_at": "2026-04-05T10:00:00Z",
                            "text": "애월 쪽에서 카페 먼저 갈까?",
                        },
                        {
                            "message_id": "msg_102",
                            "sender_id": "user_2",
                            "sender_name": "지영",
                            "sent_at": "2026-04-05T10:01:00Z",
                            "text": "조용한 곳이면 좋겠어",
                        },
                    ],
                    "previous_summary": {
                        "summary_text": "애월 지역 위주로 장소를 찾고 있다.",
                        "agreed_points": ["제주 여행", "애월 중심 동선"],
                        "open_questions": ["첫날 카페를 먼저 갈지 여부"],
                        "preferences": ["오션뷰 선호"],
                        "constraints": [],
                        "mentioned_places": [],
                        "last_message_id": "msg_100",
                    },
                }
            ]
        }
    )


class SummaryUpdateResponse(BaseModel):
    room_id: str
    summary: StructuredSummary


class ChatContext(BaseModel):
    summary: StructuredSummary | None = None
    messages_since_last_summary: list[ChatMessage] = Field(default_factory=list)
    recent_messages: list[ChatMessage] = Field(default_factory=list)


class ChatPlanRequest(BaseModel):
    team_id: str = Field(..., min_length=1)
    room_id: str = Field(..., min_length=1)
    request_message: ChatMessage
    room_context: RoomContext = Field(default_factory=RoomContext)
    chat_context: ChatContext = Field(default_factory=ChatContext)
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "team_id": "team_123",
                    "room_id": "room_456",
                    "request_message": {
                        "message_id": "msg_201",
                        "sender_id": "user_3",
                        "sender_name": "서연",
                        "sent_at": "2026-04-05T10:05:00Z",
                        "text": "애월에서 조용한 카페 추천해줘",
                    },
                    "room_context": {
                        "destination": "제주 애월",
                        "travel_dates": {
                            "start_date": "2026-05-03",
                            "end_date": "2026-05-05",
                        },
                        "participants_count": 4,
                        "bookmarked_places": [],
                        "candidate_places": [],
                    },
                    "chat_context": {
                        "summary": {
                            "summary_text": "참여자들은 애월 지역에서 조용한 카페를 우선 찾고 있다.",
                            "agreed_points": ["애월 중심으로 장소 탐색"],
                            "open_questions": [],
                            "preferences": ["조용한 분위기"],
                            "constraints": [],
                            "mentioned_places": [],
                            "last_message_id": "msg_198",
                        },
                        "messages_since_last_summary": [
                            {
                                "message_id": "msg_199",
                                "sender_name": "민수",
                                "text": "바다 보이는 곳이면 좋겠다",
                            },
                            {
                                "message_id": "msg_200",
                                "sender_name": "지영",
                                "text": "시끄러운 프랜차이즈는 별로야",
                            },
                        ],
                        "recent_messages": [
                            {
                                "message_id": "msg_199",
                                "sender_name": "민수",
                                "text": "바다 보이는 곳이면 좋겠다",
                            },
                            {
                                "message_id": "msg_200",
                                "sender_name": "지영",
                                "text": "시끄러운 프랜차이즈는 별로야",
                            },
                        ],
                    },
                }
            ]
        }
    )


class RecommendedPlace(BaseModel):
    place_id: str
    name: str
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    primary_type: str | None = None
    reason: str
    google_maps_uri: str | None = None


class ChatPlanResponse(BaseModel):
    intent: Intent
    answer_text: str
    recommended_places: list[RecommendedPlace] = Field(default_factory=list)
    updated_summary: StructuredSummary
