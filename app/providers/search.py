"""
Tavily-based SearchProvider implementation.

Wraps the web_search_service pipeline (Tavily → multi-dimension search →
credibility scoring → dedup → quality filter) behind the SearchProvider interface.
The Agent never imports search services directly.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.logging import logger
from app.providers.base import SearchProvider
from app.services.web_search_service import web_search as _web_search_svc


def _extract_price(text: str) -> Optional[float]:
    for pattern in [
        r"￥([0-9,]+\.?[0-9]*)",
        r"([0-9]+\.?[0-9]*)万元",
        r"([0-9]+\.?[0-9]*)万",
        r"([0-9,]+\.?[0-9]*)元",
    ]:
        m = re.search(pattern, text)
        if not m:
            continue
        price = float(m.group(1).replace(",", ""))
        if "万" in pattern:
            price *= 10000
        return price
    return None


def _detect_trend(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["降价", "优惠", "下调", "降低"]):
        return "down"
    if any(w in t for w in ["涨价", "上调", "上涨", "提升"]):
        return "up"
    return "stable"


def _extract_version(title: str) -> str:
    m = re.search(r"(20\d{2}款)", title)
    return m.group(1) if m else ""


class TavilySearchProvider(SearchProvider):
    """Search provider backed by Tavily Search API."""

    def __init__(self, web_search_svc=None):
        self._web = web_search_svc or _web_search_svc

    @property
    def is_available(self) -> bool:
        return self._web.is_available

    def search_car_price(
        self, brand: str, model: str, version: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        logger.info(f"[TavilySearchProvider] search_car_price: {brand} {model} {version or ''}")

        results = self._web.search_car(brand=brand, model=model, version=version, top_k=10)
        results = self._web.filter_quality(results)

        now = datetime.now(timezone.utc)
        output: List[Dict[str, Any]] = []
        for r in results:
            text = r.title + " " + r.content
            price = _extract_price(text)
            output.append({
                "brand": brand, "model": model,
                "version": version or _extract_version(r.title),
                "price": price, "currency": "CNY" if price else "",
                "trend": _detect_trend(text),
                "title": r.title, "url": r.url, "content": r.content,
                "source": r.source, "credibility_score": r.credibility_score,
                "credibility_tier": r.credibility_tier, "dimension": r.dimension,
                "published_date": r.published_date, "captured_at": now,
            })

        with_price = sum(1 for o in output if o["price"])
        logger.info(f"[TavilySearchProvider] '{brand} {model}': {len(output)} results, {with_price} with price")
        return output

    def search_news(self, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
        logger.info(f"[TavilySearchProvider] search_news: {keyword}")
        results = self._web.search_news(keyword=keyword, top_k=limit)
        results = self._web.filter_quality(results)
        return [
            {
                "title": r.title, "url": r.url, "content": r.content[:500],
                "source": r.source, "credibility_score": r.credibility_score,
                "credibility_tier": r.credibility_tier, "dimension": r.dimension,
                "published_date": r.published_date,
            }
            for r in results
        ]

    def search_general(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        logger.info(f"[TavilySearchProvider] search_general: {query[:60]}")
        return self._web.search_general(query, max_results=max_results)

    def search_comparison(
        self, car1_brand: str, car1_model: str,
        car2_brand: str, car2_model: str,
    ) -> Dict[str, Any]:
        car1 = f"{car1_brand} {car1_model}"
        car2 = f"{car2_brand} {car2_model}"
        logger.info(f"[TavilySearchProvider] search_comparison: {car1} vs {car2}")
        return self._web.search_comparison(car1, car2)
