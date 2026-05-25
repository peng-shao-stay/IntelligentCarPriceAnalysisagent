"""
Redis-based short-term chat session memory.

Falls back gracefully to DB-only mode when Redis is unreachable.
"""
from __future__ import annotations

import json
from typing import List

import redis

from app.core.config import settings
from app.core.logging import logger


class RedisMemoryManager:
    """Per-session chat history stored in Redis with automatic fallback."""

    def __init__(self, redis_url: str | None = None, ttl: int = 3600):
        self.ttl = ttl
        self._redis = None
        url = redis_url or settings.REDIS_URL
        try:
            self._redis = redis.from_url(url, socket_connect_timeout=3)
            self._redis.ping()
            logger.info(f"Redis connected: {url}")
        except Exception:
            logger.warning(
                f"Redis unavailable ({url}), falling back to DB-only mode"
            )
            self._redis = None

    @property
    def available(self) -> bool:
        return self._redis is not None

    def _key(self, session_id: str) -> str:
        return f"chat:session:{session_id}"

    def get_history(self, session_id: str) -> List[dict]:
        """Return recent chat history for a session."""
        if not self.available:
            return []
        try:
            data = self._redis.get(self._key(session_id))
            if data:
                return json.loads(data)
        except Exception:
            pass
        return []

    def append(self, session_id: str, message: dict) -> None:
        """Append a message to the session's Redis cache (max 40 messages)."""
        if not self.available:
            return
        try:
            key = self._key(session_id)
            history = self.get_history(session_id)
            history.append(message)
            if len(history) > 40:
                history = history[-40:]
            self._redis.set(
                key, json.dumps(history, ensure_ascii=False), ex=self.ttl
            )
        except Exception:
            pass

    def clear(self, session_id: str) -> None:
        """Remove the cached history for a session."""
        if not self.available:
            return
        try:
            self._redis.delete(self._key(session_id))
        except Exception:
            pass


memory_manager = RedisMemoryManager()
