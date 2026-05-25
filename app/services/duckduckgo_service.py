"""
DuckDuckGo search service — primary free search engine with Tavily fallback.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from app.core.config import settings
from app.core.logging import logger

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None


class DuckDuckGoSearchService:
    """Free web search via DuckDuckGo, with Tavily as fallback when needed."""

    def __init__(self):
        self._ddgs: Optional[DDGS] = None

    @property
    def is_available(self) -> bool:
        return DDGS is not None

    def _get_client(self) -> DDGS:
        if self._ddgs is None:
            proxy = getattr(settings, "DDG_PROXY", None) or None
            self._ddgs = DDGS(proxy=proxy)
        return self._ddgs

    def search_car_price(
        self, brand: str, model: str, version: str = None
    ) -> List[Dict]:
        """Search car prices, try DuckDuckGo first, fall back to Tavily."""
        results = self._search_web(f"{brand} {model} {version or ''} 价格 报价 官网")
        if results:
            return self._parse_price_results(results, brand, model)
        return self._tavily_fallback("search_car_price", brand, model, version)

    def search_news(self, keyword: str, limit: int = 5) -> List[Dict]:
        """Search car news."""
        results = self._search_web(f"{keyword} 汽车 最新新闻", max_results=limit)
        if results:
            return self._parse_news_results(results, limit)
        return self._tavily_fallback("search_car_news", keyword, limit=limit)

    def search_general(self, query: str, max_results: int = 5) -> List[Dict]:
        """General purpose web search."""
        results = self._search_web(query, max_results=max_results)
        if results:
            return self._parse_general_results(results)
        return self._tavily_fallback("search_general", query, max_results=max_results)

    def search_comparison(self, car1: str, car2: str) -> Dict:
        """Search car comparison."""
        query = f"{car1} vs {car2} 对比 价格 配置"
        results = self._search_web(query)
        if results:
            return {"query": query, "results": self._parse_general_results(results), "summary": ""}
        tavily_result = self._tavily_fallback("search_car_comparison", car1, car2)
        return tavily_result if isinstance(tavily_result, dict) else {"query": query, "results": [], "summary": ""}

    # ── Internal: DuckDuckGo core ──────────────────────────────

    def _search_web(self, query: str, max_results: int = 10) -> List[Dict]:
        if not self.is_available:
            logger.warning("DuckDuckGo not available (duckduckgo_search not installed)")
            return []
        try:
            client = self._get_client()
            raw = list(client.text(query, max_results=max_results))
            logger.info(f"DuckDuckGo search: '{query[:60]}' → {len(raw)} results")
            return raw
        except Exception:
            logger.debug(f"DuckDuckGo search failed, falling back to Tavily")
            return []

    # ── Result parsers ─────────────────────────────────────────

    def _parse_price_results(self, raw: List[Dict], brand: str, model: str) -> List[Dict]:
        results = []
        for item in raw:
            content = item.get("body", "") or item.get("snippet", "") or item.get("content", "")
            price = self._extract_price(content)
            results.append({
                "brand": brand,
                "model": model,
                "version": self._extract_version(item.get("title", "")),
                "price": price,
                "currency": "CNY",
                "source": item.get("source", "DuckDuckGo") or "DuckDuckGo",
                "region": "CN",
                "trend": self._detect_trend(content),
                "url": item.get("link", item.get("url", "")),
                "title": item.get("title", ""),
                "content": content[:500],
                "credibility_score": self._score_source(item.get("link", "")),
                "credibility_tier": "auto_platform",
                "dimension": "price",
                "published_date": item.get("published_date", ""),
            })
        return results

    def _parse_news_results(self, raw: List[Dict], limit: int) -> List[Dict]:
        results = []
        for item in raw[:limit]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", item.get("url", "")),
                "content": (item.get("body", "") or item.get("snippet", "") or "")[:500],
                "source": item.get("source", "DuckDuckGo") or "DuckDuckGo",
                "published_date": item.get("published_date", ""),
                "credibility_tier": "trusted_media",
            })
        return results

    def _parse_general_results(self, raw: List[Dict]) -> List[Dict]:
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("link", item.get("url", "")),
                "content": (item.get("body", "") or item.get("snippet", "") or "")[:500],
                "source": item.get("source", "DuckDuckGo") or "DuckDuckGo",
                "published_date": item.get("published_date", ""),
            }
            for item in raw
        ]

    # ── Price extraction helpers (same logic as tavily_service) ─

    def _extract_price(self, text: str) -> Optional[float]:
        patterns = [
            r"￥([0-9,]+\.?[0-9]*)",
            r"([0-9]+\.?[0-9]*)万元",
            r"([0-9]+\.?[0-9]*)万",
            r"([0-9,]+\.?[0-9]*)元",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if not match:
                continue
            price = float(match.group(1).replace(",", ""))
            if "万" in pattern:
                price *= 10000
            return price
        return None

    def _extract_version(self, title: str) -> str:
        match = re.search(r"(20\d{2}款)", title)
        return match.group(1) if match else ""

    def _detect_trend(self, text: str) -> str:
        text_lower = text.lower()
        if any(w in text_lower for w in ["降价", "优惠", "下调", "降低"]):
            return "down"
        if any(w in text_lower for w in ["涨价", "上调", "上涨", "提升"]):
            return "up"
        return "stable"

    def _score_source(self, url: str) -> int:
        if not url:
            return 50
        known = {
            "tesla.cn": 100, "byd.com": 100, "autohome.com.cn": 85,
            "dongchedi.com": 83, "yiche.com": 80, "sina.com.cn": 65,
            "163.com": 60, "qq.com": 60,
        }
        for domain, score in known.items():
            if domain in url:
                return score
        return 50

    # ── Tavily fallback ────────────────────────────────────────

    def _tavily_fallback(self, method: str, *args, **kwargs):
        try:
            from app.services.tavily_service import tavily_search
            fn = getattr(tavily_search, method, None)
            if fn:
                logger.info(f"Tavily fallback for {method}")
                return fn(*args, **kwargs)
        except Exception as exc:
            logger.warning(f"Tavily fallback failed: {exc}")
        return [] if not kwargs.get("returns_dict") else {}


duckduckgo_search = DuckDuckGoSearchService()
