from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "Travel AI Server"
    openai_api_key: str | None = None
    openai_model: str | None = None
    google_maps_api_key: str | None = None
    google_places_language_code: str = "ko"
    ai_use_mock_services: bool = False
    ai_log_level: str = "INFO"
    google_places_base_url: str = "https://places.googleapis.com/v1"
    http_timeout_seconds: float = 10.0


@lru_cache(maxsize=1)
def _read_dotenv() -> dict[str, str]:
    dotenv_path = Path(__file__).resolve().parents[2] / ".env"
    if not dotenv_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in dotenv_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _get_env_value(key: str, default: str | None = None) -> str | None:
    runtime_value = os.getenv(key)
    if runtime_value is not None:
        return runtime_value
    return _read_dotenv().get(key, default)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        openai_api_key=_get_env_value("OPENAI_API_KEY"),
        openai_model=_get_env_value("OPENAI_MODEL"),
        google_maps_api_key=_get_env_value("GOOGLE_MAPS_API_KEY"),
        google_places_language_code=_get_env_value("GOOGLE_PLACES_LANGUAGE_CODE", "ko") or "ko",
        ai_use_mock_services=_as_bool(_get_env_value("AI_USE_MOCK_SERVICES"), default=False),
        ai_log_level=_get_env_value("AI_LOG_LEVEL", "INFO") or "INFO",
    )
