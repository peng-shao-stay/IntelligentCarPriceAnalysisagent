"""
Application settings.
"""
from __future__ import annotations

import os
from typing import List, Optional

try:
    from pydantic_settings import BaseSettings
except ImportError:  # pragma: no cover - exercised only in minimal environments
    BaseSettings = None


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_list(name: str, default: List[str]) -> List[str]:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


if BaseSettings is not None:
    class Settings(BaseSettings):
        """Application settings backed by environment variables."""

        APP_NAME: str = "AutoMind AI"
        APP_VERSION: str = "0.1.0"
        DEBUG: bool = True

        API_V1_PREFIX: str = "/api/v1"

        SECRET_KEY: str = "automind-secret-key-change-in-production"
        JWT_ALGORITHM: str = "HS256"
        ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

        API_KEY: Optional[str] = None
        DEEPSEEK_API_BASE_URL: str = "https://api.deepseek.com/v1"
        DEEPSEEK_MODEL: str = "deepseek-v4-flash"

        OLLAMA_BASE_URL: str = "http://localhost:11434"
        OLLAMA_MODEL: str = "qwen3.5:9b"

        DEFAULT_MODEL: str = "primary"
        TEMPERATURE: float = 0.7
        MAX_TOKENS: int = 2000

        DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/automind"

        REDIS_URL: str = "redis://localhost:6379/0"
        REDIS_CACHE_TTL: int = 3600

        REQUEST_TIMEOUT: int = 30
        MAX_RETRIES: int = 3

        ALLOWED_ORIGINS: List[str] = ["*"]

        class Config:
            env_file = ".env"
            case_sensitive = True
else:
    class Settings:
        """Lightweight fallback when pydantic-settings is unavailable."""

        def __init__(self):
            self.APP_NAME = os.getenv("APP_NAME", "AutoMind AI")
            self.APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
            self.DEBUG = _get_bool("DEBUG", True)

            self.API_V1_PREFIX = os.getenv("API_V1_PREFIX", "/api/v1")

            self.SECRET_KEY = os.getenv("SECRET_KEY", "automind-secret-key-change-in-production")
            self.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
            self.ACCESS_TOKEN_EXPIRE_MINUTES = _get_int("ACCESS_TOKEN_EXPIRE_MINUTES", 1440)

            self.API_KEY = os.getenv("API_KEY")
            self.DEEPSEEK_API_BASE_URL = os.getenv(
                "DEEPSEEK_API_BASE_URL",
                "https://api.deepseek.com/v1",
            )
            self.DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

            self.OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            self.OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")

            self.DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "primary")
            self.TEMPERATURE = _get_float("TEMPERATURE", 0.7)
            self.MAX_TOKENS = _get_int("MAX_TOKENS", 2000)

            self.DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/automind")

            self.REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            self.REDIS_CACHE_TTL = _get_int("REDIS_CACHE_TTL", 3600)

            self.REQUEST_TIMEOUT = _get_int("REQUEST_TIMEOUT", 30)
            self.MAX_RETRIES = _get_int("MAX_RETRIES", 3)

            self.ALLOWED_ORIGINS = _get_list("ALLOWED_ORIGINS", ["*"])


settings = Settings()
