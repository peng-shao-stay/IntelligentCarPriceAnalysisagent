"""
汽车价格查询工具 — 通过 SearchProvider 接口调用，不直接依赖具体服务。

迁移说明：
  旧:  from app.agent.tools.car_price import query_car_price
       query_car_price("特斯拉", "Model 3")
  新:  from app.providers.registry import get_provider_registry
       get_provider_registry().search.search_car_price(brand="特斯拉", model="Model 3")

旧接口保持兼容，内部已切换为 Provider 调用。
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.core.logging import logger
from app.providers.base import SearchProvider


def _extract_price(text: str) -> Optional[float]:
    """Extract price value from Chinese text."""
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


def _detect_trend(text: str) -> str:
    text_lower = text.lower()
    if any(w in text_lower for w in ["降价", "优惠", "下调", "降低"]):
        return "down"
    if any(w in text_lower for w in ["涨价", "上调", "上涨", "提升"]):
        return "up"
    return "stable"


def _extract_version(title: str) -> str:
    match = re.search(r"(20\d{2}款)", title)
    return match.group(1) if match else ""


def query_car_price(
    brand: str,
    model: str,
    version: Optional[str] = None,
    *,
    provider: Optional[SearchProvider] = None,
) -> List[Dict]:
    """搜索汽车价格信息（官方售价、经销商报价、二手车价格、配置、行情、评价）

    Args:
        brand: 汽车品牌
        model: 车型
        version: 可选版本号
        provider: 可选 SearchProvider，不传则使用默认 DuckDuckGoSearchProvider

    返回按可信度排序的结果，包含从内容中提取的价格字段。
    """
    if provider is None:
        from app.providers.registry import get_provider_registry
        provider = get_provider_registry().search

    logger.info(f"Querying price for {brand} {model} {version or ''} [via Provider]")

    results = provider.search_car_price(brand=brand, model=model, version=version)

    if not results:
        logger.info(f"No results for {brand} {model}")
        return []

    with_price = sum(1 for o in results if o.get("price"))
    logger.info(
        f"Car price search '{brand} {model}': "
        f"{len(results)} results, {with_price} with price extracted "
        f"(official={sum(1 for o in results if o.get('credibility_tier') == 'official')}, "
        f"platform={sum(1 for o in results if o.get('credibility_tier') == 'auto_platform')})"
    )
    return results
