from __future__ import annotations

import logging
from functools import lru_cache

from app.clients.google_places import GooglePlacesClient, MockGooglePlacesClient, PlacesProvider
from app.clients.openai_planner import HeuristicPlanner, OpenAIPlanner, Planner
from app.core.config import _read_dotenv, Settings, get_settings
from app.services.orchestrator import OrchestratorService


@lru_cache(maxsize=1)
def _configure_logger() -> logging.Logger:
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.ai_log_level.upper(), logging.INFO))
    return logging.getLogger("ai-server")


def get_logger() -> logging.Logger:
    return _configure_logger()


@lru_cache(maxsize=1)
def get_planner() -> Planner:
    settings = get_settings()
    if settings.ai_use_mock_services or not settings.openai_api_key:
        return HeuristicPlanner()
    return OpenAIPlanner(api_key=settings.openai_api_key, model=settings.openai_model)


@lru_cache(maxsize=1)
def get_places_provider() -> PlacesProvider:
    settings = get_settings()
    if settings.ai_use_mock_services or not settings.google_maps_api_key:
        return MockGooglePlacesClient()
    return GooglePlacesClient(
        api_key=settings.google_maps_api_key,
        base_url=settings.google_places_base_url,
        language_code=settings.google_places_language_code,
        timeout_seconds=settings.http_timeout_seconds,
    )


@lru_cache(maxsize=1)
def get_orchestrator_service() -> OrchestratorService:
    return OrchestratorService(planner=get_planner(), places_provider=get_places_provider())


def reset_cached_dependencies() -> None:
    _read_dotenv.cache_clear()
    get_settings.cache_clear()
    _configure_logger.cache_clear()
    get_planner.cache_clear()
    get_places_provider.cache_clear()
    get_orchestrator_service.cache_clear()
