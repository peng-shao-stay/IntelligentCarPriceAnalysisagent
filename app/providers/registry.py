"""
ProviderRegistry — single access point for all capability providers.

The Agent receives a ProviderRegistry instance and resolves all tool
capabilities through it, without importing any concrete service directly.
"""

from __future__ import annotations

from typing import Optional

from app.core.logging import logger
from app.providers.base import DatabaseProvider, SearchProvider, VectorProvider
from app.providers.database import PostgresDatabaseProvider
from app.providers.search import TavilySearchProvider
from app.providers.vector import RAGVectorProvider


class ProviderRegistry:
    """Holds references to all capability providers.

    Thread-safe, supports lazy defaults and explicit injection for testing.
    """

    def __init__(
        self,
        *,
        search: Optional[SearchProvider] = None,
        vector: Optional[VectorProvider] = None,
        database: Optional[DatabaseProvider] = None,
    ):
        self._search = search
        self._vector = vector
        self._database = database

    # ── Lazy properties with default concrete implementations ──

    @property
    def search(self) -> SearchProvider:
        if self._search is None:
            logger.info("[ProviderRegistry] Lazy-init TavilySearchProvider")
            self._search = TavilySearchProvider()
        return self._search

    @property
    def vector(self) -> VectorProvider:
        if self._vector is None:
            logger.info("[ProviderRegistry] Lazy-init RAGVectorProvider")
            self._vector = RAGVectorProvider()
        return self._vector

    @property
    def database(self) -> DatabaseProvider:
        if self._database is None:
            logger.info("[ProviderRegistry] Lazy-init PostgresDatabaseProvider")
            self._database = PostgresDatabaseProvider()
        return self._database

    # ── Test / injection helpers ──

    def with_search(self, provider: SearchProvider) -> "ProviderRegistry":
        """Return a new registry with an overridden search provider (builder pattern)."""
        return ProviderRegistry(search=provider, vector=self._vector, database=self._database)

    def with_vector(self, provider: VectorProvider) -> "ProviderRegistry":
        """Return a new registry with an overridden vector provider."""
        return ProviderRegistry(search=self._search, vector=provider, database=self._database)


# ── Module-level default (lazy — no providers created until first access) ──

_default_registry: Optional[ProviderRegistry] = None


def get_provider_registry() -> ProviderRegistry:
    """Return the process-wide default ProviderRegistry (lazy singleton)."""
    global _default_registry
    if _default_registry is None:
        _default_registry = ProviderRegistry()
    return _default_registry


def reset_provider_registry() -> None:
    """Reset the default registry (useful for tests)."""
    global _default_registry
    _default_registry = None
