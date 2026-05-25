"""
Abstract provider interfaces.

Each interface defines the contract that concrete providers must fulfill.
The Agent depends on these interfaces, never on concrete implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class SearchProvider(ABC):
    """Web search capability — car prices, news, comparisons, general search."""

    @abstractmethod
    def is_available(self) -> bool:
        """Whether the search backend is configured and reachable."""
        ...

    @abstractmethod
    def search_car_price(
        self,
        brand: str,
        model: str,
        version: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search for car pricing information across multiple dimensions.

        Returns a list of result dicts, each containing:
        brand, model, version, price, currency, trend, title, url, content,
        source, credibility_score, credibility_tier, dimension, published_date.
        """
        ...

    @abstractmethod
    def search_news(
        self,
        keyword: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search for automotive news by keyword.

        Returns a list of result dicts, each containing:
        title, url, content, source, credibility_score, credibility_tier,
        dimension, published_date.
        """
        ...

    @abstractmethod
    def search_general(
        self,
        query: str,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """General-purpose web search for any query.

        Returns a list of result dicts with title, url, content, source, published_date.
        """
        ...

    @abstractmethod
    def search_comparison(
        self,
        car1_brand: str,
        car1_model: str,
        car2_brand: str,
        car2_model: str,
    ) -> Dict[str, Any]:
        """Search for comparison data between two specific cars.

        Returns a dict with keys: car1, car2, results (list), summary (str).
        """
        ...


class VectorProvider(ABC):
    """Vector / embedding-based semantic search over the knowledge base."""

    @abstractmethod
    def search(
        self,
        db,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Semantic vector search over ingested documents.

        Returns chunks ranked by cosine distance, with document metadata.
        """
        ...

    @abstractmethod
    def embed_query(self, query: str) -> List[float]:
        """Generate an embedding vector for a single query string."""
        ...

    @abstractmethod
    def build_context(
        self,
        db,
        query: str,
        top_k: int = 5,
    ) -> str:
        """Build an LLM-ready context string from knowledge base results."""
        ...


class DatabaseProvider(ABC):
    """Structured database access — session management and typed queries."""

    @abstractmethod
    def create_session(self):
        """Create and return a new SQLAlchemy database session.

        The caller is responsible for closing the session.
        """
        ...

    @abstractmethod
    def close_session(self, session) -> None:
        """Safely close a database session."""
        ...
