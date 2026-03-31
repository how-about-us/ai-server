from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.chat import Intent


class PlannerDecision(BaseModel):
    intent: Intent
    search_query: str | None = None
    place_type: str | None = None
    clarification_question: str | None = None
    unsupported_reason: str | None = None
    extracted_preferences: list[str] = Field(default_factory=list)
    party_size: int | None = None
    destination: str | None = None


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


class SummaryPayload(BaseModel):
    answer_text: str
    grounds: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str
    destination: str | None = None
    place_type: str | None = None
    max_results: int = Field(default=5, ge=1, le=10)
