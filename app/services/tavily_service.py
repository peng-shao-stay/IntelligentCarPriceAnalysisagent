"""
Tavily Search API service — purpose-built for AI agents.

Tavily returns search results with cleaned page content, no separate page
extraction needed. Works from China without proxy.

- Endpoint: POST https://api.tavily.com/search
- Auth: api_key in request body
- Free tier: 1,000 queries/month
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.core.config import settings
from app.core.logging import logger
from app.utils.helpers import create_httpx_client, extract_domain


class TavilySearchService:
    """Search via Tavily API — built for AI agent workflows."""

    BASE_URL = "https://api.tavily.com/search"

    def __init__(self):
        self._client = create_httpx_client(timeout=15)

    @property
    def is_available(self) -> bool:
        return bool(settings.TAVILY_API_KEY)

    def search(
        self,
        query: str,
        max_results: int = 10,
        search_depth: str = "advanced",
        include_answer: bool = False,
    ) -> List[Dict]:
        """Execute a Tavily search.

        Args:
            query: Search query.
            max_results: Max results to return (max 20).
            search_depth: 'basic' (faster) or 'advanced' (deeper, includes raw_content).
            include_answer: Whether to include a generated answer summary.

        Returns list of dicts: {title, url, content, raw_content, score}.
        """
        if not self.is_available:
            logger.warning("Tavily not available: TAVILY_API_KEY not set")
            return []

        payload = {
            "api_key": settings.TAVILY_API_KEY,
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_answer": include_answer,
            "include_raw_content": (search_depth == "advanced"),
        }

        try:
            resp = self._client.post(self.BASE_URL, json=payload)
            if resp.status_code != 200:
                logger.warning(f"Tavily API error {resp.status_code}: {resp.text[:300]}")
                return []

            data = resp.json()
            results = data.get("results", [])

            output = []
            for r in results:
                output.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", ""),          # cleaned page text
                    "raw_content": r.get("raw_content", ""),   # full raw text (advanced only)
                    "score": r.get("score", 0.0),
                    "source": extract_domain(r.get("url", "")),
                    "published_date": r.get("published_date", ""),
                })

            logger.info(f"Tavily search: '{query[:60]}' → {len(output)} results (depth={search_depth})")
            return output

        except Exception as exc:
            logger.warning(f"Tavily search failed for '{query[:60]}': {exc}")
            return []

tavily_search = TavilySearchService()
