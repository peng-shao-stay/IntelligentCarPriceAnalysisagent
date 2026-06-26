"""
LangChain-style function tools for LLM function calling.

Tools:
  - get_web_data    → DuckDuckGo web search
  - search_knowledge → RAG knowledge base

The LLM decides which tool to call (if any) based on the user's question.
"""
from __future__ import annotations

from typing import Callable, Optional

from langchain_core.tools import tool as langchain_tool

from app.core.logging import logger


@langchain_tool
def get_web_data(query: str) -> str:
    """使用 Tavily AI 搜索引擎实时搜索互联网信息。

    Tavily 专为 AI Agent 设计，返回结果包含清理后的页面正文，无需额外提取。

    适用场景：
    - 用户询问最新资讯、新闻、价格等需要实时数据的问题
    - 用户明确要求联网搜索
    - 问题需要当前/最新的信息而非训练数据

    Args:
        query: 搜索关键词，用中文或英文，要具体。

    注意：如果搜索失败或无结果，请直接用训练知识回答用户，不要再调用此工具。
    """
    try:
        from app.services.tavily_service import tavily_search

        if not tavily_search.is_available:
            return (
                "[搜索不可用] Tavily API Key 未配置。\n"
                "请直接用训练知识回答用户，不要再尝试搜索。"
            )

        results = tavily_search.search(query, max_results=5, search_depth="advanced")
        if not results:
            return (
                f"[搜索未获取到结果] 关键词「{query}」未能获取到有效搜索结果。\n"
                "**请直接用你的训练知识回答用户的问题，不要再尝试搜索。**"
            )

        lines = [f"搜索结果（共 {len(results)} 条，Tavily 搜索）："]
        for i, r in enumerate(results, 1):
            title = r.get("title", "无标题")
            content = (r.get("content") or "")[:500]
            raw = (r.get("raw_content") or "")[:1000]
            url = r.get("url", "")
            source = r.get("source", "未知")
            score = r.get("score", 0)

            lines.append(f"\n[{i}] {title}")
            lines.append(f"   来源: {source} | 相关度: {score:.2f}")
            if url:
                lines.append(f"   链接: {url}")
            lines.append(f"   内容: {content}")
            if raw:
                lines.append(f"   全文: {raw}")

        return "\n".join(lines)

    except Exception as exc:
        logger.warning(f"get_web_data tool error: {exc}")
        return (
            f"[搜索失败] 网络错误：{exc}\n"
            "**请直接用训练知识回答用户的问题，不要再尝试搜索。**"
        )


def _build_search_knowledge(db_session_factory: Optional[Callable] = None):
    """Create a search_knowledge tool bound to the RAG service.

    Args:
        db_session_factory: A callable that returns a new DB session.
    """

    @langchain_tool
    def search_knowledge(query: str) -> str:
        """查询本地知识库中的汽车信息。

        适用场景：
        - 用户询问汽车参数、配置、历史价格等本地知识库已有的信息
        - 用户查询的是不需要联网的汽车专业知识
        - 联网搜索结果不足时作为补充

        Args:
            query: 搜索查询，如 "比亚迪汉 参数配置" 或 "特斯拉 Model 3 历史价格"。

        注意：如果查询失败或无结果，请直接用训练知识回答用户，不要再调用此工具。
        """
        if db_session_factory is None:
            return (
                "[知识库不可用] 数据库未连接。\n"
                "请直接用训练知识回答用户的问题，不要再尝试查询知识库。"
            )

        try:
            from app.providers.registry import get_provider_registry

            providers = get_provider_registry()
            if providers is None or providers.vector is None:
                return (
                    "[知识库不可用] 向量检索服务未初始化。\n"
                    "请直接用训练知识回答用户的问题。"
                )

            if db_session_factory is not None:
                db = db_session_factory()
            else:
                db = None

            if db is None:
                return (
                    "[知识库不可用] 数据库未连接。\n"
                    "请直接用训练知识回答用户的问题。"
                )

            try:
                results = providers.vector.search(db, query, top_k=5)
                if not results:
                    return (
                        f"[知识库无结果] 未找到与「{query}」相关的内容。\n"
                        "**请直接用训练知识回答用户的问题，不要再查询知识库。**"
                    )

                lines = [f"知识库结果（共 {len(results)} 条）："]
                for i, r in enumerate(results, 1):
                    title = r.get("title", "无标题")
                    content = (r.get("content") or "")[:300]
                    source_url = r.get("source_url", "")
                    score = r.get("score", r.get("similarity", 0))
                    lines.append(f"\n[{i}] {title}（相关度: {score:.2f}）")
                    if source_url:
                        lines.append(f"   来源: {source_url}")
                    lines.append(f"   内容: {content}")
                return "\n".join(lines)

            finally:
                if hasattr(db, "close"):
                    db.close()

        except Exception as exc:
            logger.warning(f"search_knowledge tool error: {exc}")
            return (
                f"[知识库查询失败] {exc}\n"
                "**请直接用训练知识回答用户的问题。**"
            )

    return search_knowledge


# ── Tool builder ────────────────────────────────────────────────


class FunctionToolset:
    """Container for function-calling tools with their definitions."""

    def __init__(self, db_session_factory: Optional[Callable] = None):
        self.get_web_data = get_web_data
        self.search_knowledge = _build_search_knowledge(db_session_factory)
        self._all: Optional[list] = None

    @property
    def all(self) -> list:
        """Return all tools as a list for bind_tools()."""
        if self._all is None:
            self._all = [self.get_web_data, self.search_knowledge]
        return self._all

    @property
    def by_name(self) -> dict:
        """Return tools keyed by name."""
        return {
            "get_web_data": self.get_web_data,
            "search_knowledge": self.search_knowledge,
        }
