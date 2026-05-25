"""
汽车新闻搜索工具 — 通过 SearchProvider 接口调用，不直接依赖具体搜索服务。

迁移说明：
  旧:  from app.agent.tools.news_search import search_news
       search_news("新能源汽车")
  新:  from app.providers.registry import get_provider_registry
       get_provider_registry().search.search_news(keyword="新能源汽车")

旧接口保持兼容，内部已切换为 Provider 调用。
summarize_news() 是纯 LLM 格式化工具，无需更改。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.agent.prompts import NEWS_SUMMARY_PROMPT
from app.core.logging import logger
from app.providers.base import SearchProvider


def search_news(
    keyword: str,
    limit: int = 10,
    *,
    provider: Optional[SearchProvider] = None,
) -> List[Dict]:
    """搜索汽车新闻（最新资讯、行业动态、技术动态）

    Args:
        keyword: 搜索关键词
        limit: 返回数量上限
        provider: 可选 SearchProvider，不传则使用默认 TavilySearchProvider

    返回按可信度排序的结果列表。
    """
    if provider is None:
        from app.providers.registry import get_provider_registry
        provider = get_provider_registry().search

    logger.info(f"Searching news with keyword: {keyword} [via Provider]")

    if not provider.is_available:
        logger.warning(f"Search provider not available for news: {keyword}")
        return []

    results = provider.search_news(keyword=keyword, limit=limit)

    logger.info(
        f"News search '{keyword}': {len(results)} results "
        f"(tier1={sum(1 for n in results if n.get('credibility_tier') in ('official','trusted_media'))})"
    )
    return results


def get_brand_news(
    brand: str,
    limit: int = 10,
    *,
    provider: Optional[SearchProvider] = None,
) -> List[Dict]:
    """Get recent news for a specific brand."""
    return search_news(keyword=brand, limit=limit, provider=provider)


def summarize_news(news_list: List[Dict], llm_client=None) -> str:
    """Summarize a list of news articles — pure formatting function, no external I/O."""
    logger.info(f"Summarizing {len(news_list)} news articles")

    if not news_list:
        return "暂无相关新闻。"

    if llm_client and getattr(llm_client, "is_available", False):
        news_content = "\n\n".join(
            f"标题: {item.get('title', '')}\n内容: {item.get('content', '')}"
            for item in news_list[:3]
        )
        prompt = NEWS_SUMMARY_PROMPT.format(news_content=news_content)
        try:
            return llm_client.chat([{"role": "user", "content": prompt}])
        except Exception as exc:
            logger.warning(f"LLM news summary failed, using fallback summary: {exc}")

    top_titles = [item.get("title", "未命名资讯") for item in news_list[:3]]
    joined_titles = "；".join(top_titles)
    return f"最近的重点资讯包括：{joined_titles}。如果你需要，我可以继续展开其中某一条。"
