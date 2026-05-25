"""
RAG-based VectorProvider implementation.

Wraps the RAG service (semantic chunking + pgvector embeddings + vector search)
behind the VectorProvider interface.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.logging import logger
from app.providers.base import VectorProvider
from app.services.rag_service import rag_service as _rag_svc


class RAGVectorProvider(VectorProvider):
    """Vector search provider backed by RAG service (Ollama bge-m3 + pgvector)."""

    def __init__(self, rag_svc=None):
        self._rag = rag_svc or _rag_svc

    def search(
        self,
        db,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        logger.info(f"[RAGVectorProvider] search: '{query[:60]}' (top_k={top_k})")
        return self._rag.search(db, query, top_k=top_k, filters=filters)

    def embed_query(self, query: str) -> List[float]:
        return self._rag.embed_query(query)

    def build_context(
        self,
        db,
        query: str,
        top_k: int = 5,
    ) -> str:
        logger.info(f"[RAGVectorProvider] build_context: '{query[:60]}'")
        return self._rag.build_context(db, query, top_k=top_k)
