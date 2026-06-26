"""
Searcher Agent — Tavily Search API 联网搜索
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.multi_agent.base import AgentResult, BaseAgent
from app.core.logging import logger


class SearcherAgent(BaseAgent):
    """搜索 Agent：负责所有联网搜索（Tavily Search API）。"""

    name = "searcher"

    def search_car_price(
        self, brand: str, model: str, version: str = None
    ) -> AgentResult:
        if self.providers and hasattr(self.providers, 'search') and self.providers.search is not None:
            try:
                results = self.providers.search.search_car_price(brand, model, version)
                if results:
                    return AgentResult.ok(results)
            except Exception as exc:
                logger.warning(f"Searcher: provider search_car_price failed: {exc}")
        return AgentResult.fail(f"未查到 {brand} {model} 的价格信息")

    def search_news(self, keyword: str, limit: int = 5) -> AgentResult:
        if self.providers and hasattr(self.providers, 'search') and self.providers.search is not None:
            try:
                results = self.providers.search.search_news(keyword, limit)
                if results:
                    return AgentResult.ok(results)
            except Exception as exc:
                logger.warning(f"Searcher: provider search_news failed: {exc}")
        return AgentResult.fail(f"未查到 '{keyword}' 相关新闻")

    def search_comparison(self, car1: str, car2: str) -> AgentResult:
        if self.providers and hasattr(self.providers, 'search') and self.providers.search is not None:
            try:
                result = self.providers.search.search_comparison(
                    car1, "", car2, "",
                )
                return AgentResult.ok(result)
            except Exception as exc:
                logger.warning(f"Searcher: provider search_comparison failed: {exc}")
        return AgentResult.fail(f"对比 {car1} vs {car2} 失败")

    def search_general(self, query: str, max_results: int = 5) -> AgentResult:
        if self.providers and hasattr(self.providers, 'search') and self.providers.search is not None:
            try:
                results = self.providers.search.search_general(query, max_results=max_results)
                if results:
                    return AgentResult.ok(results)
            except Exception as exc:
                logger.warning(f"Searcher: provider search_general failed: {exc}")
        return AgentResult.fail("搜索无结果")
