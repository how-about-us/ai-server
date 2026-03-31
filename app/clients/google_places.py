from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from app.schemas.planner import PlaceCandidate, SearchRequest


class PlacesProvider(Protocol):
    async def search_places(self, request: SearchRequest) -> list[PlaceCandidate]:
        ...

    async def get_place_details(self, place_id: str) -> PlaceCandidate | None:
        ...


@dataclass(frozen=True)
class MockPlaceRecord:
    place_id: str
    name: str
    address: str
    lat: float
    lng: float
    primary_type: str
    tags: tuple[str, ...]


MOCK_PLACES: tuple[MockPlaceRecord, ...] = (
    MockPlaceRecord(
        place_id="mock-aewol-cafe-1",
        name="애월 바다정원",
        address="제주 제주시 애월읍 애월해안로 100",
        lat=33.4610,
        lng=126.3090,
        primary_type="cafe",
        tags=("제주", "애월", "카페", "오션뷰", "브런치"),
    ),
    MockPlaceRecord(
        place_id="mock-aewol-cafe-2",
        name="하늘카페 애월",
        address="제주 제주시 애월읍 곽지길 21",
        lat=33.4504,
        lng=126.3059,
        primary_type="cafe",
        tags=("제주", "애월", "카페", "조용한"),
    ),
    MockPlaceRecord(
        place_id="mock-seongsu-brunch-1",
        name="성수 브런치랩",
        address="서울 성동구 성수동2가 310-70",
        lat=37.5444,
        lng=127.0555,
        primary_type="restaurant",
        tags=("서울", "성수", "브런치", "식당"),
    ),
    MockPlaceRecord(
        place_id="mock-busan-seafood-1",
        name="광안리 바다식탁",
        address="부산 수영구 광안해변로 210",
        lat=35.1531,
        lng=129.1187,
        primary_type="restaurant",
        tags=("부산", "광안리", "해산물", "저녁", "식당"),
    ),
    MockPlaceRecord(
        place_id="mock-jeju-attraction-1",
        name="애월 해안 산책로",
        address="제주 제주시 애월읍 해안로 25",
        lat=33.4627,
        lng=126.3118,
        primary_type="tourist_attraction",
        tags=("제주", "애월", "산책", "관광", "오션뷰"),
    ),
)


class MockGooglePlacesClient:
    async def search_places(self, request: SearchRequest) -> list[PlaceCandidate]:
        tokens = {token.strip().lower() for token in request.query.split() if token.strip()}
        if request.destination:
            tokens.update(part.lower() for part in request.destination.split())
        requested_type = (request.place_type or "").lower()

        results: list[PlaceCandidate] = []
        for record in MOCK_PLACES:
            record_tokens = {tag.lower() for tag in record.tags}
            type_match = not requested_type or record.primary_type == requested_type
            keyword_match = not tokens or bool(tokens & record_tokens)
            if type_match and keyword_match:
                results.append(
                    PlaceCandidate(
                        place_id=record.place_id,
                        name=record.name,
                        address=record.address,
                        lat=record.lat,
                        lng=record.lng,
                        primary_type=record.primary_type,
                        google_maps_uri=f"https://www.google.com/maps/search/?api=1&query={record.lat},{record.lng}",
                    )
                )
        return results[: request.max_results]

    async def get_place_details(self, place_id: str) -> PlaceCandidate | None:
        for record in MOCK_PLACES:
            if record.place_id == place_id:
                return PlaceCandidate(
                    place_id=record.place_id,
                    name=record.name,
                    address=record.address,
                    lat=record.lat,
                    lng=record.lng,
                    primary_type=record.primary_type,
                    google_maps_uri=f"https://www.google.com/maps/search/?api=1&query={record.lat},{record.lng}",
                )
        return None


class GooglePlacesClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        language_code: str = "ko",
        timeout_seconds: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._language_code = language_code
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def search_places(self, request: SearchRequest) -> list[PlaceCandidate]:
        payload = {
            "textQuery": request.query,
            "languageCode": self._language_code,
            "maxResultCount": request.max_results,
        }
        headers = {
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.formattedAddress,"
                "places.location,places.primaryType,places.googleMapsUri,"
                "places.rating,places.userRatingCount"
            ),
        }
        response = await self._client.post(
            f"{self._base_url}/places:searchText",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return [self._to_candidate(item) for item in data.get("places", [])]

    async def get_place_details(self, place_id: str) -> PlaceCandidate | None:
        headers = {
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": (
                "id,displayName,formattedAddress,location,primaryType,"
                "googleMapsUri,rating,userRatingCount"
            ),
        }
        response = await self._client.get(
            f"{self._base_url}/places/{place_id}",
            headers=headers,
            params={"languageCode": self._language_code},
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return self._to_candidate(response.json())

    async def aclose(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _to_candidate(item: dict) -> PlaceCandidate:
        location = item.get("location") or {}
        display_name = item.get("displayName") or {}
        return PlaceCandidate(
            place_id=item.get("id", ""),
            name=display_name.get("text", ""),
            address=item.get("formattedAddress"),
            lat=location.get("latitude"),
            lng=location.get("longitude"),
            primary_type=item.get("primaryType"),
            google_maps_uri=item.get("googleMapsUri"),
            rating=item.get("rating"),
            user_rating_count=item.get("userRatingCount"),
        )
