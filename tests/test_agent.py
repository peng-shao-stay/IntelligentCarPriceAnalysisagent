"""
Unit tests for the AutoMind agent — consultant edition (v2).
Phase 1: Tests use Provider injection instead of patching concrete tool imports.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.agent.agent import AutoMindAgent
from app.providers.base import DatabaseProvider, SearchProvider, VectorProvider
from app.providers.registry import ProviderRegistry


# ═══════════════════════════════════════════════════════════════
#  Fakes
# ═══════════════════════════════════════════════════════════════

class FakeLLM:
    def __init__(self):
        self.is_available = True
        self.calls = []

    def chat(self, messages, system_prompt=None, model_type=None):
        self.calls.append(
            {
                "messages": messages,
                "system_prompt": system_prompt,
                "model_type": model_type,
            }
        )
        return messages[-1]["content"]


class FakeSearchProvider(SearchProvider):
    """Injectable fake — returns pre-configured results and records calls."""

    def __init__(self):
        self._available = True
        self.car_price_results: list = []
        self.news_results: list = []
        self.general_results: list = []
        self.comparison_results: dict = {}
        # Call records for assertions
        self.car_price_calls: list = []
        self.news_calls: list = []
        self.general_calls: list = []
        self.comparison_calls: list = []

    def is_available(self) -> bool:
        return self._available

    def search_car_price(self, brand, model, version=None):
        self.car_price_calls.append({"brand": brand, "model": model, "version": version})
        return list(self.car_price_results)  # shallow copy so mutations don't leak

    def search_news(self, keyword, limit=10):
        self.news_calls.append({"keyword": keyword, "limit": limit})
        return list(self.news_results)

    def search_general(self, query, max_results=5):
        self.general_calls.append({"query": query, "max_results": max_results})
        return list(self.general_results)

    def search_comparison(self, car1_brand, car1_model, car2_brand, car2_model):
        self.comparison_calls.append({
            "car1_brand": car1_brand, "car1_model": car1_model,
            "car2_brand": car2_brand, "car2_model": car2_model,
        })
        return dict(self.comparison_results)


class FakeVectorProvider(VectorProvider):
    """Minimal stub — returns empty results by default."""

    def __init__(self):
        self.search_results: list = []

    def search(self, db, query, top_k=5, filters=None):
        return list(self.search_results)

    def embed_query(self, query):
        return [0.0] * 1024

    def build_context(self, db, query, top_k=5):
        return ""


class FakeDatabaseProvider(DatabaseProvider):
    """Minimal stub — raises if used (most tests don't hit the DB path)."""

    def create_session(self):
        raise RuntimeError("FakeDatabaseProvider.create_session called unexpectedly")

    def close_session(self, session) -> None:
        pass


# ═══════════════════════════════════════════════════════════════
#  Tests
# ═══════════════════════════════════════════════════════════════

class TestAutoMindAgent(unittest.TestCase):
    def setUp(self):
        self.fake_llm = FakeLLM()
        self.fake_search = FakeSearchProvider()
        self.fake_vector = FakeVectorProvider()
        self.fake_database = FakeDatabaseProvider()
        self.providers = ProviderRegistry(
            search=self.fake_search,
            vector=self.fake_vector,
            database=self.fake_database,
        )
        self.agent = AutoMindAgent(
            llm_client=self.fake_llm,
            providers=self.providers,
        )

    # ── Intent detection (unchanged) ─────────────────────────

    def test_detect_intent_price_query(self):
        self.assertEqual(self.agent._detect_intent("特斯拉 Model 3 多少钱"), "car_price")

    def test_detect_intent_comparison(self):
        self.assertEqual(self.agent._detect_intent("对比一下比亚迪汉和特斯拉 Model 3"), "car_compare")

    def test_detect_intent_news(self):
        self.assertEqual(self.agent._detect_intent("最近有什么汽车新闻"), "news")

    def test_detect_intent_general(self):
        self.assertEqual(self.agent._detect_intent("你好"), "general")

    # ── Tool execution + template response ───────────────────

    def test_price_query_runs_tool_and_uses_template(self):
        self.fake_search.car_price_results = [
            {
                "brand": "Tesla",
                "model": "Model 3",
                "version": "后轮驱动版",
                "price": 231900,
                "currency": "CNY",
                "source": "Tesla Official",
            }
        ]

        response = self.agent.process_message("特斯拉 Model 3 多少钱", web_search=True)

        self.assertEqual(len(self.fake_search.car_price_calls), 1)
        self.assertIn("车型体系总览", response)
        self.assertIn("版本定位分析", response)
        self.assertIn("关键参数对比", response)
        self.assertIn("购车分析与推荐", response)
        self.assertIn("Tesla", response)
        self.assertIn("Model 3", response)

    def test_price_query_missing_car_info_returns_clarification(self):
        response = self.agent.process_message("帮我看看价格")
        self.assertIn("品牌和车型", response)
        self.assertEqual(len(self.fake_llm.calls), 0)

    def test_comparison_query_runs_tools_and_uses_template(self):
        # Two cars → two separate search_car_price calls
        self.fake_search.car_price_results = [
            {"brand": "比亚迪", "model": "汉", "price": 189800, "currency": "CNY", "source": "Source A"},
        ]

        response = self.agent.process_message("对比一下比亚迪汉和特斯拉 Model 3", web_search=True)

        # extract_multiple_car_info should parse two cars → two provider calls
        self.assertGreaterEqual(len(self.fake_search.car_price_calls), 1)
        # Verify 8-section comparison template (via orchestrator → writer)
        self.assertIn("三行核心总结", response)
        self.assertIn("参数对比表", response)
        self.assertIn("A车型优点", response)
        self.assertIn("B车型优点", response)
        self.assertIn("适合人群", response)
        self.assertIn("最终建议", response)

    def test_news_query_runs_tools_and_uses_template(self):
        self.fake_search.news_results = [
            {"title": "小米 SU7 销量更新", "content": "销量表现强劲", "source": "News"}
        ]

        response = self.agent.process_message("最近有什么小米汽车新闻", web_search=True)

        self.assertEqual(len(self.fake_search.news_calls), 1)
        # Verify news template sections (via orchestrator → writer)
        self.assertIn("头条要闻", response)
        self.assertIn("资讯速览", response)
        self.assertIn("小米", response)

    # ── General chat ─────────────────────────────────────────

    def test_general_chat_includes_history_summary(self):
        history = [
            {"role": "user", "content": "我预算20万左右"},
            {"role": "assistant", "content": "你更在意空间还是智能化？"},
        ]

        response = self.agent.process_message("我更在意智能化", history=history)

        self.assertIn("历史上下文", response)
        self.assertIn("预算20万左右", response)
        self.assertIn("我更在意智能化", response)

    # ── Planner integration ──────────────────────────────────

    def test_price_trend_style_selected_for_trend_keywords(self):
        self.fake_search.car_price_results = [
            {
                "brand": "Tesla",
                "model": "Model 3",
                "version": "后轮驱动版",
                "price": 231900,
                "currency": "CNY",
                "trend": "down",
                "source": "Tesla Official",
            }
        ]

        response = self.agent.process_message("特斯拉 Model 3 最近降价了吗", web_search=True)

        self.assertEqual(len(self.fake_search.car_price_calls), 1)
        self.assertIn("历史价格走势", response)
        self.assertIn("当前市场行情", response)
        self.assertIn("入手时机分析", response)

    def test_no_llm_fallback_returns_graceful_message(self):
        """When LLM is unavailable, fallback returns a graceful message."""
        agent_no_llm = AutoMindAgent(
            llm_client=FakeLLM(),
            providers=self.providers,
        )
        agent_no_llm.llm_service.is_available = False

        self.fake_search.car_price_results = [
            {
                "brand": "Tesla",
                "model": "Model 3",
                "version": "后轮驱动版",
                "price": 231900,
                "currency": "CNY",
                "source": "Tesla Official",
            }
        ]
        response = agent_no_llm.process_message("特斯拉 Model 3 价格", web_search=True)
        self.assertTrue(len(response) > 0)
        self.assertIn("LLM", response)


if __name__ == "__main__":
    unittest.main(verbosity=2)
