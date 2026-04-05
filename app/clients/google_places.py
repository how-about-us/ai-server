from __future__ import annotations

from typing import Protocol

import httpx

from app.schemas.planner import PlaceCandidate, SearchRequest


class PlacesProvider(Protocol):
    async def search_places(self, request: SearchRequest) -> list[PlaceCandidate]:
        ...

    async def get_place_details(self, place_id: str) -> PlaceCandidate | None:
        ...


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
