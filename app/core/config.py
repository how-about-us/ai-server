from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    google_maps_api_key: str
    app_name: str = "Travel AI Server"
    openai_model: str = "gpt-5.4-mini"
    google_places_language_code: str = "ko"
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


def _require_env_value(key: str) -> str:
    value = _get_env_value(key)
    if value is None or not value.strip():
        raise RuntimeError(f"Required environment variable '{key}' is missing.")
    return value.strip()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        openai_api_key=_require_env_value("OPENAI_API_KEY"),
        google_maps_api_key=_require_env_value("GOOGLE_MAPS_API_KEY"),
        openai_model=_get_env_value("OPENAI_MODEL", "gpt-5.4-mini") or "gpt-5.4-mini",
        google_places_language_code=_get_env_value("GOOGLE_PLACES_LANGUAGE_CODE", "ko") or "ko",
        ai_log_level=_get_env_value("AI_LOG_LEVEL", "INFO") or "INFO",
    )
