"""
Web search service — multi-dimensional parallel search + credibility scoring + dedup.

Backend: Tavily Search API (built for AI agents, includes page content extraction).
"""
from __future__ import annotations

import hashlib
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, List, Tuple
from app.core.logging import logger
from app.services.tavily_service import tavily_search
from app.utils.helpers import extract_domain

# ── Source credibility tiers ──────────────────────────────────

_CREDIBILITY_TIERS: Dict[str, int] = {
    "tesla.cn": 100, "byd.com": 100, "nio.cn": 100, "lixiang.com": 100,
    "xiaomiev.com": 100, "bmw.com.cn": 100, "mercedes-benz.com.cn": 100,
    "audi.cn": 100, "porsche.com": 100, "toyota.com.cn": 100,
    "honda.com.cn": 100, "volvocars.com": 100, "zeekrlife.com": 100,
    "xpeng.com": 100,
    "autohome.com.cn": 85, "dongchedi.com": 83, "yiche.com": 80,
    "bitauto.com": 80, "pcauto.com.cn": 75, "xcar.com.cn": 72, "cheshi.com": 70,
    "sina.com.cn": 65, "sohu.com": 60, "163.com": 60, "qq.com": 60,
    "ifeng.com": 58, "thepaper.cn": 65, "36kr.com": 55, "geekpark.net": 55,
    "ithome.com": 50,
    "zhihu.com": 40, "xiaohongshu.com": 35, "douyin.com": 30,
    "bilibili.com": 35, "weibo.com": 25, "tieba.baidu.com": 20,
}

_OFFICIAL_DOMAINS = {
    "tesla", "byd", "nio", "lixiang", "xiaomiev", "bmw", "mercedes-benz",
    "audi", "porsche", "toyota", "honda", "volvocars", "zeekrlife", "xpeng",
    "aion", "hiphi", "avtr", "arcfox", "voyah",
}

_AUTO_PLATFORM_DOMAINS = {
    "autohome", "dongchedi", "yiche", "bitauto", "pcauto", "xcar", "cheshi",
}


@dataclass
class SearchResult:
    """Single search result with credibility metadata."""

    title: str
    url: str
    content: str
    source: str
    published_date: str = ""
    credibility_score: int = 0
    credibility_tier: str = "unknown"
    dimension: str = "general"
    relevance_score: float = 0.0

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(
            (self.url + self.title + self.content[:200]).encode()
        ).hexdigest()[:16]


# ── Search dimensions ──────────────────────────────────────────

SEARCH_DIMENSIONS = {
    "price_official": {"suffix": "官方售价 厂商指导价", "weight": 1.0},
    "price_dealer":  {"suffix": "经销商报价 4S店报价 优惠", "weight": 0.9},
    "price_used":    {"suffix": "二手车价格 二手报价 保值率", "weight": 0.7},
    "config":        {"suffix": "配置参数 续航 马力 电池", "weight": 0.8},
    "market":        {"suffix": "市场行情 销量 价格走势", "weight": 0.7},
    "reviews":       {"suffix": "用户评价 口碑 优缺点", "weight": 0.6},
}

NEWS_SEARCH_DIMENSIONS = {
    "latest_news": {"suffix": "最新消息 新闻", "weight": 1.0},
    "industry":    {"suffix": "行业动态 政策 补贴", "weight": 0.7},
    "tech":        {"suffix": "新技术 智能驾驶 电池技术", "weight": 0.6},
}


class WebSearchService:
    """Multi-dimensional search with credibility assessment.

    Backend: Tavily Search API.
    """

    def __init__(self, max_workers: int = 6):
        self.max_workers = max_workers

    @property
    def is_available(self) -> bool:
        return tavily_search.is_available

    # ── Public API ─────────────────────────────────────────

    def search_car(
        self, brand: str, model: str, version: str = None,
        dimensions: List[str] = None, top_k: int = 10,
    ) -> List[SearchResult]:
        """Multi-dimensional car price search."""
        if not self.is_available:
            logger.warning("Tavily search unavailable. Set TAVILY_API_KEY.")
            return []

        car_key = f"{brand} {model}" + (f" {version}" if version else "")
        dims_to_search = dimensions or list(SEARCH_DIMENSIONS.keys())

        all_results: List[SearchResult] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for dim_key in dims_to_search:
                dim_config = SEARCH_DIMENSIONS.get(dim_key)
                if not dim_config:
                    continue
                query = f"{car_key} {dim_config['suffix']}"
                futures[
                    executor.submit(self._search_dimension, query, dim_key, dim_config["weight"])
                ] = dim_key

            for future in as_completed(futures):
                dim_key = futures[future]
                try:
                    results = future.result()
                    all_results.extend(results)
                except Exception as exc:
                    logger.warning(f"Dimension '{dim_key}' failed: {exc}")

        all_results = self._finalize_results(all_results)
        logger.info(f"Car search '{car_key}': {len(all_results)} results from {len(dims_to_search)} dims")
        return all_results[:top_k]

    def search_news(
        self, keyword: str, dimensions: List[str] = None, top_k: int = 10,
    ) -> List[SearchResult]:
        """Multi-dimensional news search."""
        if not self.is_available:
            return []

        dims_to_search = dimensions or list(NEWS_SEARCH_DIMENSIONS.keys())
        all_results: List[SearchResult] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for dim_key in dims_to_search:
                dim_config = NEWS_SEARCH_DIMENSIONS.get(dim_key)
                if not dim_config:
                    continue
                query = f"{keyword} {dim_config['suffix']}"
                futures[
                    executor.submit(self._search_dimension, query, dim_key, dim_config["weight"])
                ] = dim_key

            for future in as_completed(futures):
                try:
                    results = future.result()
                    all_results.extend(results)
                except Exception as exc:
                    logger.warning(f"News dimension failed: {exc}")

        all_results = self._finalize_results(all_results)
        return all_results[:top_k]

    def search_comparison(self, car1: str, car2: str) -> Dict:
        """Search for comparison between two cars.

        Uses the same pipeline as search_car/search_news: search → score → dedup.
        """
        query = f"{car1} vs {car2} 对比 价格 配置"
        results = self._search_dimension(query, "comparison", weight=1.0)
        if not results:
            return {"car1": car1, "car2": car2, "results": [], "summary": ""}

        results = self._finalize_results(results)
        # Build backward-compatible output dict
        scored = [
            {
                "title": r.title, "url": r.url, "content": r.content[:500],
                "source": r.source, "credibility_score": r.credibility_score,
                "credibility_tier": r.credibility_tier,
            }
            for r in results[:5]
        ]
        summary_parts = [r["content"][:200] for r in scored[:3] if r["content"]]
        return {
            "car1": car1, "car2": car2,
            "results": scored,
            "summary": "\n\n".join(summary_parts) if summary_parts else "",
        }

    def search_general(self, query: str, max_results: int = 5) -> List[Dict]:
        """General web search via Tavily."""
        return tavily_search.search(query, max_results=max_results, search_depth="basic")

    def _finalize_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """Shared tail: score credibility → dedup → sort by composite score."""
        for r in results:
            r.credibility_score, r.credibility_tier = self._score_source(r.url, r.source)
        results = self._deduplicate(results)
        results.sort(
            key=lambda r: (r.credibility_score * 0.6 + r.relevance_score * 0.4),
            reverse=True,
        )
        return results

    # ── Internal ───────────────────────────────────────────

    def _search_dimension(self, query: str, dimension: str, weight: float) -> List[SearchResult]:
        raw = tavily_search.search(query, max_results=5)
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("content", ""),
                source=r.get("source", ""),
                published_date=r.get("published_date", ""),
                dimension=dimension,
                relevance_score=weight * (r.get("score", 0.5) or 0.5),
            )
            for r in raw if r.get("content")
        ]

    def _score_source(self, url: str, source: str) -> Tuple[int, str]:
        domain = extract_domain(url)
        source_lower = (source or "").lower()

        for known, score in _CREDIBILITY_TIERS.items():
            if known in domain or known in source_lower:
                if score >= 90:     return score, "official"
                if score >= 70:     return score, "auto_platform"
                if score >= 50:     return score, "trusted_media"
                return score, "social_media"

        for brand in _OFFICIAL_DOMAINS:
            if brand in domain:
                return 90, "official"
        for plat in _AUTO_PLATFORM_DOMAINS:
            if plat in domain:
                return 75, "auto_platform"
        if any(domain.endswith(t) for t in [".gov.cn", ".org.cn", ".edu.cn"]):
            return 80, "official"
        if any(kw in domain for kw in
               ["xinhua", "people", "cctv", "chinanews", "ce.cn", "yicai",
                "cls.cn", "caixin", "thepaper", "36kr", "geekpark"]):
            return 60, "trusted_media"
        if any(kw in domain for kw in ["news", "daily", "times", "post", "media", "press"]):
            return 55, "trusted_media"
        if any(kw in source_lower for kw in ["新闻", "资讯", "日报", "时报", "财经", "汽车"]):
            return 45, "trusted_media"

        return 30, "unknown"


    def _deduplicate(self, results: List[SearchResult]) -> List[SearchResult]:
        seen_urls, seen_hashes = set(), set()
        unique: List[SearchResult] = []
        for r in results:
            if r.url and r.url in seen_urls:
                continue
            h = r.content_hash
            if h in seen_hashes:
                continue
            seen_urls.add(r.url)
            seen_hashes.add(h)
            existing = next(
                (x for x in unique if x.dimension == r.dimension and x.content_hash[:8] == h[:8]),
                None,
            )
            if existing:
                if r.credibility_score > existing.credibility_score:
                    unique.remove(existing)
                    unique.append(r)
            else:
                unique.append(r)
        return unique

    def filter_quality(
        self, results: List[SearchResult], min_score: int = 20, min_content_len: int = 30,
    ) -> List[SearchResult]:
        return [
            r for r in results
            if r.credibility_score >= min_score
            and len(r.content) >= min_content_len
            and not self._is_spam(r)
        ]

    def _is_spam(self, result: SearchResult) -> bool:
        spam_patterns = [
            r"广告推广", r"点击购买", r"扫码咨询", r"加微信咨询",
            r"免费领取", r"限时抢购", r"一键拨号",
        ]
        text = result.title + result.content
        return any(re.search(p, text) for p in spam_patterns)


web_search = WebSearchService()
