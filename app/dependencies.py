from __future__ import annotations

import logging
from functools import lru_cache

from app.clients.google_places import GooglePlacesClient
from app.clients.openai_travel import OpenAITravelClient
from app.core.config import _get_env_value, _read_dotenv, get_settings
from app.services.orchestrator import ChatPlanService
from app.services.summary import SummaryService


@lru_cache(maxsize=1)
def _configure_logger() -> logging.Logger:
    log_level = (_get_env_value("AI_LOG_LEVEL", "INFO") or "INFO").upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
    return logging.getLogger("ai-server")


def get_logger() -> logging.Logger:
    return _configure_logger()


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAITravelClient:
    settings = get_settings()
    return OpenAITravelClient(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )


@lru_cache(maxsize=1)
def get_summary_service() -> SummaryService:
    return SummaryService(ai_client=get_openai_client())


@lru_cache(maxsize=1)
def get_places_provider() -> GooglePlacesClient:
    settings = get_settings()
    return GooglePlacesClient(
        api_key=settings.google_maps_api_key,
        base_url=settings.google_places_base_url,
        language_code=settings.google_places_language_code,
        timeout_seconds=settings.http_timeout_seconds,
    )


@lru_cache(maxsize=1)
def get_chat_plan_service() -> ChatPlanService:
    return ChatPlanService(
        summary_service=get_summary_service(),
        ai_client=get_openai_client(),
        places_provider=get_places_provider(),
    )


def reset_cached_dependencies() -> None:
    _read_dotenv.cache_clear()
    get_settings.cache_clear()
    _configure_logger.cache_clear()
    get_openai_client.cache_clear()
    get_summary_service.cache_clear()
    get_places_provider.cache_clear()
    get_chat_plan_service.cache_clear()
