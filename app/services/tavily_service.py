"""
Tavily search service with lazy initialization.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from app.core.config import settings
from app.core.logging import logger

try:
    from langchain_tavily import TavilyExtract, TavilySearch
except ImportError:  # pragma: no cover - exercised only in minimal environments
    TavilyExtract = None
    TavilySearch = None


class TavilySearchService:
    """Thin wrapper around Tavily search and extraction tools."""

    def __init__(self):
        self.search_tool = None
        self.extract_tool = None

    @property
    def is_available(self) -> bool:
        return bool(settings.TAVILY_API_KEY and TavilySearch is not None and TavilyExtract is not None)

    def _ensure_initialized(self):
        if not self.is_available:
            return False
        if self.search_tool is None:
            self.search_tool = TavilySearch(
                tavily_api_key=settings.TAVILY_API_KEY,
                max_results=5,
                search_depth="advanced",
            )
        if self.extract_tool is None:
            self.extract_tool = TavilyExtract(
                tavily_api_key=settings.TAVILY_API_KEY,
                max_num_pages=3,
            )
        return True

    def search_car_price(self, brand: str, model: str, version: str = None) -> List[Dict]:
        if not self._ensure_initialized():
            logger.warning("Tavily search is unavailable. Returning empty price results.")
            return []

        query = f"{brand} {model}"
        if version:
            query += f" {version}"
        query += " 价格 官网 报价"

        try:
            results = self.search_tool.invoke({"query": query})
            actual_results = results.get("results", []) if isinstance(results, dict) else results
            car_prices = self._parse_search_results(actual_results, brand, model)
            logger.info(f"Found {len(car_prices)} price records from Tavily")
            return car_prices
        except Exception as exc:  # pragma: no cover - depends on remote API
            logger.error(f"Tavily price search failed: {exc}")
            return []

    def extract_page_content(self, urls: List[str]) -> List[Dict]:
        if not self._ensure_initialized():
            logger.warning("Tavily extract is unavailable. Returning no page content.")
            return []

        try:
            results = self.extract_tool.invoke({"urls": urls[:3]})
        except Exception as exc:  # pragma: no cover - depends on remote API
            logger.error(f"Tavily extract failed: {exc}")
            return []

        extracted_contents = []
        for result in results:
            if isinstance(result, dict):
                extracted_contents.append(
                    {
                        "url": result.get("url", ""),
                        "title": result.get("title", ""),
                        "content": result.get("content", ""),
                        "raw_content": result.get("raw_content", ""),
                    }
                )
        return extracted_contents

    def search_car_comparison(self, car1: str, car2: str) -> Dict:
        if not self._ensure_initialized():
            logger.warning("Tavily comparison search is unavailable.")
            return {}

        query = f"{car1} vs {car2} 对比 价格 配置 哪个好"
        try:
            results = self.search_tool.invoke({"query": query})
        except Exception as exc:  # pragma: no cover - depends on remote API
            logger.error(f"Tavily comparison search failed: {exc}")
            return {}

        actual_results = results.get("results", []) if isinstance(results, dict) else results
        return {
            "query": query,
            "results": actual_results,
            "summary": self._summarize_comparison(actual_results),
        }

    def search_car_news(self, brand_or_keyword: str, limit: int = 5) -> List[Dict]:
        if not self._ensure_initialized():
            logger.warning("Tavily news search is unavailable. Returning no news results.")
            return []

        query = f"{brand_or_keyword} 汽车 最新新闻"
        try:
            results = self.search_tool.invoke({"query": query})
        except Exception as exc:  # pragma: no cover - depends on remote API
            logger.error(f"Tavily news search failed: {exc}")
            return []

        actual_results = results.get("results", []) if isinstance(results, dict) else results
        if not isinstance(actual_results, list):
            return []

        news_list = []
        for result in actual_results[:limit]:
            if not isinstance(result, dict):
                continue
            news_list.append(
                {
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": result.get("content", "")[:500],
                    "source": result.get("source", ""),
                    "published_date": result.get("published_date", ""),
                }
            )
        return news_list

    def search_general(self, query: str, max_results: int = 5) -> List[Dict]:
        """General-purpose web search for any query."""
        if not self._ensure_initialized():
            logger.warning("Tavily search is unavailable.")
            return []

        try:
            results = self.search_tool.invoke({"query": query})
        except Exception as exc:
            logger.error(f"Tavily general search failed: {exc}")
            return []

        actual_results = results.get("results", []) if isinstance(results, dict) else results
        if not isinstance(actual_results, list):
            return []

        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "source": r.get("source", ""),
                "published_date": r.get("published_date", ""),
            }
            for r in actual_results[:max_results]
            if isinstance(r, dict) and r.get("content")
        ]

    def _parse_search_results(self, results, brand: str, model: str) -> List[Dict]:
        car_prices: List[Dict] = []
        if isinstance(results, str):
            price = self._extract_price(results)
            if price:
                car_prices.append(
                    {
                        "brand": brand,
                        "model": model,
                        "version": "未知版本",
                        "price": price,
                        "currency": "CNY",
                        "source": "Tavily Search",
                        "region": "CN",
                        "trend": self._detect_trend(results),
                        "url": "",
                        "captured_at": None,
                    }
                )
            return car_prices

        if not isinstance(results, list):
            return car_prices

        for result in results:
            if not isinstance(result, dict):
                continue

            content = result.get("content", "")
            price = self._extract_price(content)
            if price:
                car_prices.append(
                    {
                        "brand": brand,
                        "model": model,
                        "version": self._extract_version(result.get("title", "")),
                        "price": price,
                        "currency": "CNY",
                        "source": result.get("source", "Tavily Search"),
                        "region": "CN",
                        "trend": self._detect_trend(content),
                        "url": result.get("url", ""),
                        "captured_at": None,
                    }
                )
        return car_prices

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
        if match:
            return match.group(1)
        return "未知版本"

    def _detect_trend(self, text: str) -> str:
        text_lower = text.lower()
        if any(word in text_lower for word in ["降价", "优惠", "下调", "降低"]):
            return "down"
        if any(word in text_lower for word in ["涨价", "上调", "上涨", "提升"]):
            return "up"
        return "stable"

    def _summarize_comparison(self, results: List[Dict]) -> str:
        if not results:
            return "未找到对比信息。"

        summary_parts = []
        for result in results[:3]:
            if isinstance(result, dict) and result.get("content"):
                summary_parts.append(result["content"][:200])
        return "\n\n".join(summary_parts)


tavily_search = TavilySearchService()
