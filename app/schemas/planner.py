from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.chat import Intent


class IntentDecision(BaseModel):
    intent: Intent
    destination: str | None = None
    place_type: str | None = None
    search_query: str | None = None


class PlaceCandidate(BaseModel):
    place_id: str
    name: str
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    primary_type: str | None = None
    google_maps_uri: str | None = None
    rating: float | None = None
    user_rating_count: int | None = None


class SearchRequest(BaseModel):
    query: str
    destination: str | None = None
    place_type: str | None = None
    max_results: int = Field(default=5, ge=1, le=10)


class ChatAnswerDraft(BaseModel):
    answer_text: str


class PlaceRecommendationDraft(BaseModel):
    answer_text: str
    place_reasons: list[str] = Field(default_factory=list)
