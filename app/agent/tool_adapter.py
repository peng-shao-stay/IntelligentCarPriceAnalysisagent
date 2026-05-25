"""
ToolAdapter — compatibility bridge between old Tool Calling and new Provider Pattern.

This module is the SINGLE entry point for all tool-like operations in the agent.
It wraps Provider calls behind the legacy tool function signatures, ensuring:

  1. Old callers continue to work without changes
  2. New code can use providers directly
  3. All external service access goes through the provider layer

Architecture:

  Old Tool Calling (兼容)          New Provider Pattern (推荐)
  ─────────────────────           ─────────────────────────
  tool_adapter.query_car_price()  →  providers.search.search_car_price()
  tool_adapter.search_news()      →  providers.search.search_news()
  tool_adapter.search_vector()    →  providers.vector.search()
  tool_adapter.get_db_session()   →  providers.database.create_session()

Usage:

  # Recommended: use providers directly
  from app.providers.registry import get_provider_registry
  registry = get_provider_registry()
  results = registry.search.search_car_price(brand="特斯拉", model="Model 3")

  # Compatible: use tool adapter (delegates to providers internally)
  from app.agent.tool_adapter import query_car_price
  results = query_car_price("特斯拉", "Model 3")
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.logging import logger
from app.providers.base import DatabaseProvider, SearchProvider, VectorProvider
from app.providers.registry import get_provider_registry


# ═══════════════════════════════════════════════════════════════
#  Search operations
# ═══════════════════════════════════════════════════════════════

def query_car_price(
    brand: str,
    model: str,
    version: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """[兼容] 查询汽车价格 — 委托给 SearchProvider.search_car_price()"""
    return get_provider_registry().search.search_car_price(
        brand=brand, model=model, version=version,
    )


def search_news(
    keyword: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """[兼容] 搜索汽车新闻 — 委托给 SearchProvider.search_news()"""
    return get_provider_registry().search.search_news(
        keyword=keyword, limit=limit,
    )


def search_general(
    query: str,
    max_results: int = 5,
) -> List[Dict[str, Any]]:
    """[兼容] 通用网页搜索 — 委托给 SearchProvider.search_general()"""
    return get_provider_registry().search.search_general(
        query=query, max_results=max_results,
    )


def search_comparison(
    car1_brand: str,
    car1_model: str,
    car2_brand: str,
    car2_model: str,
) -> Dict[str, Any]:
    """[兼容] 车型对比搜索 — 委托给 SearchProvider.search_comparison()"""
    return get_provider_registry().search.search_comparison(
        car1_brand=car1_brand,
        car1_model=car1_model,
        car2_brand=car2_brand,
        car2_model=car2_model,
    )


# ═══════════════════════════════════════════════════════════════
#  Vector / RAG operations
# ═══════════════════════════════════════════════════════════════

def search_vector(
    db,
    query: str,
    top_k: int = 5,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """[兼容] 向量语义搜索 — 委托给 VectorProvider.search()"""
    return get_provider_registry().vector.search(
        db=db, query=query, top_k=top_k, filters=filters,
    )


def build_rag_context(
    db,
    query: str,
    top_k: int = 5,
) -> str:
    """[兼容] 构建 RAG 上下文 — 委托给 VectorProvider.build_context()"""
    return get_provider_registry().vector.build_context(
        db=db, query=query, top_k=top_k,
    )


# ═══════════════════════════════════════════════════════════════
#  Database operations
# ═══════════════════════════════════════════════════════════════

def create_db_session():
    """[兼容] 创建数据库会话 — 委托给 DatabaseProvider.create_session()"""
    return get_provider_registry().database.create_session()


def close_db_session(session) -> None:
    """[兼容] 关闭数据库会话 — 委托给 DatabaseProvider.close_session()"""
    get_provider_registry().database.close_session(session)
