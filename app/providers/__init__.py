"""
Provider Pattern — abstract tool layer for the AutoMind agent.

Phase 1 (COMPLETE): All agent tool dependencies are abstracted behind provider interfaces.
The Agent depends on interfaces, never on concrete implementations.

Architecture:

  Agent / Consumer
       │
       ▼
  ProviderRegistry  ──  lazy singleton, supports DI for testing
       │
       ├── SearchProvider    ──  DuckDuckGoSearchProvider   (web search)
       ├── VectorProvider    ──  RAGVectorProvider      (semantic / RAG search)
       └── DatabaseProvider  ──  PostgresDatabaseProvider (DB sessions)

Usage:

  # Recommended: inject via registry
  from app.providers.registry import get_provider_registry
  registry = get_provider_registry()
  results = registry.search.search_car_price(brand="特斯拉", model="Model 3")

  # For testing: inject fakes
  from app.providers.registry import ProviderRegistry
  registry = ProviderRegistry(search=FakeSearchProvider())

  # Compatible: use tool_adapter (delegates to providers)
  from app.agent.tool_adapter import query_car_price
  results = query_car_price("特斯拉", "Model 3")

Migration from old Tool Calling:
  Old:  from app.agent.tools.car_price import query_car_price
  New:  from app.providers.registry import get_provider_registry
        get_provider_registry().search.search_car_price(brand=..., model=...)
"""

from app.providers.base import DatabaseProvider, SearchProvider, VectorProvider
from app.providers.database import PostgresDatabaseProvider
from app.providers.registry import ProviderRegistry, get_provider_registry, reset_provider_registry
from app.providers.search import DuckDuckGoSearchProvider
from app.providers.vector import RAGVectorProvider

__all__ = [
    # Interfaces
    "SearchProvider",
    "VectorProvider",
    "DatabaseProvider",
    # Implementations
    "DuckDuckGoSearchProvider",
    "RAGVectorProvider",
    "PostgresDatabaseProvider",
    # Registry
    "ProviderRegistry",
    "get_provider_registry",
    "reset_provider_registry",
]
