"""
Searcher Agent — 联网搜索，DuckDuckGo 优先 + Tavily 兜底
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.multi_agent.base import AgentResult, BaseAgent
from app.core.logging import logger
from app.services.duckduckgo_service import duckduckgo_search
from app.services.tavily_service import tavily_search


class SearcherAgent(BaseAgent):
    """搜索 Agent：负责所有联网搜索，自动 fallback。"""

    name = "searcher"

    def search_car_price(
        self, brand: str, model: str, version: str = None
    ) -> AgentResult:
        # Use injected providers first (tests rely on this)
        if self.providers and hasattr(self.providers, 'search') and self.providers.search is not None:
            try:
                results = self.providers.search.search_car_price(brand, model, version)
                if results:
                    return AgentResult.ok(results)
            except Exception:
                pass
        results = duckduckgo_search.search_car_price(brand, model, version)
        if not results:
            results = tavily_search.search_car_price(brand, model, version)
        if not results:
            return AgentResult.fail(f"未查到 {brand} {model} 的价格信息")
        logger.info(f"Searcher: found {len(results)} price results for {brand} {model}")
        return AgentResult.ok(results)

    def search_news(self, keyword: str, limit: int = 5) -> AgentResult:
        if self.providers and hasattr(self.providers, 'search') and self.providers.search is not None:
            try:
                results = self.providers.search.search_news(keyword, limit)
                if results:
                    return AgentResult.ok(results)
            except Exception:
                pass
        results = duckduckgo_search.search_news(keyword, limit)
        if not results:
            raw = tavily_search.search_car_news(keyword, limit)
            results = raw if isinstance(raw, list) else []
        if not results:
            return AgentResult.fail(f"未查到 '{keyword}' 相关新闻")
        return AgentResult.ok(results)

    def search_comparison(self, car1: str, car2: str) -> AgentResult:
        result = duckduckgo_search.search_comparison(car1, car2)
        if not result.get("results"):
            raw = tavily_search.search_car_comparison(car1, car2)
            result = raw if isinstance(raw, dict) else {"results": []}
        return AgentResult.ok(result)

    def search_general(self, query: str, max_results: int = 5) -> AgentResult:
        results = duckduckgo_search.search_general(query, max_results)
        if not results:
            results = tavily_search.search_general(query, max_results)
        return AgentResult.ok(results) if results else AgentResult.fail("搜索无结果")
