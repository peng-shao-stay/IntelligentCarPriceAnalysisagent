"""
Utility helpers for text extraction and formatting.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

import httpx

from app.core.logging import logger


def create_httpx_client(*, timeout: int = 30) -> httpx.Client:
    """Create an httpx.Client with HTTP/1.1 and SSL verify disabled.

    HTTP/2 is disabled for Ollama compatibility; SSL verify is disabled
    to avoid Windows Python cert store issues.
    """
    transport = httpx.HTTPTransport(http2=False, verify=False, retries=0)
    return httpx.Client(transport=transport, timeout=timeout)

BRAND_ALIASES = {
    "特斯拉": "Tesla",
    "tesla": "Tesla",
    "比亚迪": "比亚迪",
    "byd": "比亚迪",
    "蔚来": "蔚来",
    "nio": "蔚来",
    "小鹏": "小鹏",
    "xpeng": "小鹏",
    "理想": "理想",
    "li auto": "理想",
    "问界": "问界",
    "小米": "小米",
}

MODEL_PATTERNS = [
    r"model\s*[3ysx]",
    r"海豹",
    r"海狮",
    r"汉",
    r"秦",
    r"宋",
    r"唐",
    r"元",
    r"问界\s*m?[579]",
    r"理想\s*l[6789]",
    r"小米\s*su7",
    r"et5",
    r"et7",
    r"es6",
    r"g6",
    r"g9",
    r"p7",
]

VERSION_PATTERNS = [
    r"20\d{2}款",
    r"后轮驱动版",
    r"长续航版",
    r"高性能版",
    r"标准版",
    r"四驱版",
    r"旗舰版",
]


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def extract_car_info(text: str) -> dict:
    """Extract a single car description from free-form text."""
    normalized_text = normalize_whitespace(text)
    lowered = normalized_text.lower()

    brand = None
    for alias, canonical in BRAND_ALIASES.items():
        if alias in lowered:
            brand = canonical
            break

    model = None
    for pattern in MODEL_PATTERNS:
        match = re.search(pattern, normalized_text, re.IGNORECASE)
        if match:
            model = match.group(0).strip()
            if model.lower().startswith("model"):
                model = model.title()
            break

    if brand is None and model and model.lower().startswith("model"):
        brand = "Tesla"

    version = None
    for pattern in VERSION_PATTERNS:
        match = re.search(pattern, normalized_text, re.IGNORECASE)
        if match:
            version = match.group(0).strip()
            break

    return {
        "brand": brand,
        "model": model,
        "version": version,
    }


def extract_multiple_car_info(text: str, max_cars: int = 4) -> List[dict]:
    """Extract multiple cars for comparison requests."""
    segments = [
        segment.strip()
        for segment in re.split(r"\bvs\b|VS|对比|比较|和|与|跟|及", text)
        if segment.strip()
    ]

    cars: List[dict] = []
    seen = set()

    for segment in segments:
        info = extract_car_info(segment)
        key = (info.get("brand"), info.get("model"), info.get("version"))
        if (info.get("brand") or info.get("model")) and key not in seen:
            cars.append(info)
            seen.add(key)
        if len(cars) >= max_cars:
            return cars

    if len(cars) >= 2:
        return cars

    for alias, canonical in BRAND_ALIASES.items():
        for match in re.finditer(re.escape(alias), text, re.IGNORECASE):
            window = text[match.start(): match.start() + 32]
            info = extract_car_info(window)
            if not info.get("brand"):
                info["brand"] = canonical
            key = (info.get("brand"), info.get("model"), info.get("version"))
            if (info.get("brand") or info.get("model")) and key not in seen:
                cars.append(info)
                seen.add(key)
            if len(cars) >= max_cars:
                return cars

    return cars[:max_cars]


def extract_news_keyword(text: str) -> str:
    """Extract a concise keyword for news lookup."""
    car_info = extract_car_info(text)
    if car_info.get("brand") and car_info.get("model"):
        return f"{car_info['brand']} {car_info['model']}"
    if car_info.get("brand"):
        return car_info["brand"]

    cleaned = re.sub(r"[？?。!！,，]", " ", text)
    cleaned = re.sub(r"(最新|新闻|资讯|消息|最近|帮我|看看|一下|汽车)", " ", cleaned)
    cleaned = normalize_whitespace(cleaned)
    return cleaned or "汽车"


def format_price(price: float, currency: str = "CNY") -> str:
    if price is None:
        return "暂无价格"
    if currency == "CNY":
        return f"￥{price:,.2f}"
    if currency == "USD":
        return f"${price:,.2f}"
    return f"{price:,.2f} {currency}"


def calculate_discount(original_price: float, current_price: float) -> dict:
    discount_amount = original_price - current_price
    discount_rate = (discount_amount / original_price * 100) if original_price > 0 else 0
    return {
        "original_price": original_price,
        "current_price": current_price,
        "discount_amount": discount_amount,
        "discount_rate": round(discount_rate, 2),
    }


def validate_url(url: str) -> bool:
    pattern = re.compile(
        r"^https?://"
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
        r"localhost|"
        r"\d{1,3}(?:\.\d{1,3}){3})"
        r"(?::\d+)?"
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    return url is not None and pattern.match(url) is not None


def parse_date(date_string: str) -> Optional[datetime]:
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y年%m月%d日",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue

    logger.warning(f"Unable to parse date: {date_string}")
    return None


# ═══════════════════════════════════════════════════════════════
#  Semantic Chunking Engine — re-exported from app.utils.chunking
# ═══════════════════════════════════════════════════════════════

from app.utils.chunking import (  # noqa: E402, F401 — backward-compatible re-exports
    estimate_tokens,
    identify_brand,
    identify_model,
    identify_all_brands,
    extract_metadata as extract_structured_metadata,
    generate_keywords as generate_retrieval_keywords,
    build_embedding_content,
    structured_chunk,
    BM25Scorer,
    tokenize_query,
    fuse_scores,
    _BRAND_MAP,
)


# Legacy aliases — kept for backward compatibility
def semantic_chunk(
    text: str,
    target_tokens: int = 800,
    min_tokens: int = 400,
    max_tokens: int = 1000,
    overlap_tokens: int = 150,
) -> List[str]:
    """Backward-compatible: returns just the content strings from structured_chunk."""
    from app.utils.chunking import structured_chunk as _structured_chunk
    result = _structured_chunk(text)
    return [c.content for c in result.all_chunks]


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    """Backward-compatible wrapper. Delegates to semantic_chunk."""
    return semantic_chunk(text, target_tokens=chunk_size // 2,
                          min_tokens=max(100, chunk_size // 4),
                          max_tokens=chunk_size // 2,
                          overlap_tokens=overlap // 2)


def classify_chunk_type(text: str, metadata: dict) -> str:
    """Backward-compatible: classify text into chunk_type."""
    from app.utils.chunking import identify_all_brands, _MODEL_RE
    lowered = text.lower()
    brands = identify_all_brands(text)
    if len(brands) >= 2:
        return "comparison"
    has_brand = bool(metadata.get("brand"))
    has_model = bool(metadata.get("model"))
    if has_brand and has_model:
        return "model"
    if has_brand and not has_model:
        return "brand"
    return "model"


def extract_car_info_from_text(text: str) -> dict:
    """Backward-compatible: extract brand and model."""
    brand = identify_brand(text)
    model = identify_model(text, brand=brand)
    return {"brand": brand, "model": model}


# Internal helpers re-exported for code that imports them directly
_SENTENCE_END_RE = __import__('re').compile(r'(?<=[。！？；.!?])\s*')
