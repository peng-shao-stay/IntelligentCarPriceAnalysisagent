"""
第一阶段：网页搜索服务 — 多维度并行搜索 + 来源可信度评估 + 去重
"""
from __future__ import annotations

import hashlib
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from app.core.config import settings
from app.core.logging import logger
from app.services.duckduckgo_service import duckduckgo_search

# ── Source credibility tiers ──────────────────────────────────

# Score mapping: higher = more credible
_CREDIBILITY_TIERS: Dict[str, int] = {
    # Tier 1: Official sources (score 90-100)
    "tesla.cn": 100,
    "byd.com": 100,
    "nio.cn": 100,
    "lixiang.com": 100,
    "xiaomiev.com": 100,
    "bmw.com.cn": 100,
    "mercedes-benz.com.cn": 100,
    "audi.cn": 100,
    "porsche.com": 100,
    "toyota.com.cn": 100,
    "honda.com.cn": 100,
    "volvocars.com": 100,
    "zeekrlife.com": 100,
    "xpeng.com": 100,
    # Tier 2: Major auto platforms (score 70-89)
    "autohome.com.cn": 85,
    "汽车之家": 85,
    "dongchedi.com": 83,
    "懂车帝": 83,
    "yiche.com": 80,
    "易车": 80,
    "bitauto.com": 80,
    "pcauto.com.cn": 75,
    "太平洋汽车": 75,
    "xcar.com.cn": 72,
    "爱卡汽车": 72,
    "cheshi.com": 70,
    # Tier 3: Trusted media (score 50-69)
    "sina.com.cn": 65,
    "sohu.com": 60,
    "163.com": 60,
    "qq.com": 60,
    "ifeng.com": 58,
    "thepaper.cn": 65,
    "36kr.com": 55,
    "geekpark.net": 55,
    "ithome.com": 50,
    # Tier 4: Other / unknown (score 10-40)
    "zhihu.com": 40,
    "xiaohongshu.com": 35,
    "douyin.com": 30,
    "bilibili.com": 35,
    "weibo.com": 25,
    "tieba.baidu.com": 20,
}

# Domain patterns for tier classification
_OFFICIAL_DOMAINS = {
    "tesla", "byd", "nio", "lixiang", "xiaomiev", "bmw", "mercedes-benz",
    "audi", "porsche", "toyota", "honda", "volvocars", "zeekrlife", "xpeng",
    "liauto", "nio", "aion", "hiphi", "avtr", "arcfox", "voyah", "im motors",
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


# ── Search dimensions (what to search for each car query) ─────

SEARCH_DIMENSIONS = {
    "price_official": {
        "suffix": "官方售价 厂商指导价",
        "weight": 1.0,
        "description": "官方售价",
    },
    "price_dealer": {
        "suffix": "经销商报价 4S店报价 优惠",
        "weight": 0.9,
        "description": "经销商报价",
    },
    "price_used": {
        "suffix": "二手车价格 二手报价 保值率",
        "weight": 0.7,
        "description": "二手车价格",
    },
    "config": {
        "suffix": "配置参数 续航 马力 电池",
        "weight": 0.8,
        "description": "配置信息",
    },
    "market": {
        "suffix": "市场行情 销量 价格走势",
        "weight": 0.7,
        "description": "市场行情",
    },
    "reviews": {
        "suffix": "用户评价 口碑 优缺点",
        "weight": 0.6,
        "description": "用户评价",
    },
}

NEWS_SEARCH_DIMENSIONS = {
    "latest_news": {
        "suffix": "最新消息 新闻",
        "weight": 1.0,
        "description": "最新资讯",
    },
    "industry": {
        "suffix": "行业动态 政策 补贴",
        "weight": 0.7,
        "description": "行业动态",
    },
    "tech": {
        "suffix": "新技术 智能驾驶 电池技术",
        "weight": 0.6,
        "description": "技术动态",
    },
}


class WebSearchService:
    """Multi-dimensional car price and news search with credibility assessment."""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers

    @property
    def is_available(self) -> bool:
        return duckduckgo_search.is_available

    # ── Public API ─────────────────────────────────────────

    def search_car(
        self,
        brand: str,
        model: str,
        version: str = None,
        dimensions: List[str] = None,
        top_k: int = 10,
    ) -> List[SearchResult]:
        """Execute multi-dimensional car price search in parallel.

        Args:
            brand: Car brand (e.g. 特斯拉)
            model: Car model (e.g. Model 3)
            version: Optional version string
            dimensions: Which dimensions to search (default: all price dimensions)
            top_k: Max results to return after dedup and ranking

        Returns:
            Ranked search results with credibility scores
        """
        if not self.is_available:
            logger.warning("Web search unavailable. DuckDuckGo may not be installed.")
            return []

        car_key = f"{brand} {model}" + (f" {version}" if version else "")
        dims_to_search = dimensions or list(SEARCH_DIMENSIONS.keys())

        # Phase 1: Parallel search across dimensions
        all_results: List[SearchResult] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for dim_key in dims_to_search:
                dim_config = SEARCH_DIMENSIONS.get(dim_key)
                if not dim_config:
                    continue
                query = f"{car_key} {dim_config['suffix']}"
                futures[
                    executor.submit(
                        self._search_single_dimension, query, dim_key, dim_config["weight"]
                    )
                ] = dim_key

            for future in as_completed(futures):
                dim_key = futures[future]
                try:
                    results = future.result()
                    all_results.extend(results)
                    logger.debug(f"Dimension '{dim_key}': {len(results)} results")
                except Exception as exc:
                    logger.warning(f"Dimension '{dim_key}' search failed: {exc}")

        # Phase 2: Score credibility
        for r in all_results:
            r.credibility_score, r.credibility_tier = self._score_source(r.url, r.source)

        # Phase 3: Deduplicate
        all_results = self._deduplicate(all_results)

        # Phase 4: Rank by composite score
        all_results.sort(
            key=lambda r: (r.credibility_score * 0.6 + r.relevance_score * 0.4),
            reverse=True,
        )

        logger.info(
            f"Car search '{car_key}': {len(all_results)} unique results "
            f"from {len(dims_to_search)} dimensions"
        )
        return all_results[:top_k]

    def search_news(
        self,
        keyword: str,
        dimensions: List[str] = None,
        top_k: int = 10,
    ) -> List[SearchResult]:
        """Execute multi-dimensional news search in parallel."""
        if not self.is_available:
            logger.warning("Web search unavailable.")
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
                    executor.submit(
                        self._search_single_dimension, query, dim_key, dim_config["weight"]
                    )
                ] = dim_key

            for future in as_completed(futures):
                dim_key = futures[future]
                try:
                    results = future.result()
                    all_results.extend(results)
                except Exception as exc:
                    logger.warning(f"News dimension '{dim_key}' failed: {exc}")

        for r in all_results:
            r.credibility_score, r.credibility_tier = self._score_source(r.url, r.source)

        all_results = self._deduplicate(all_results)
        all_results.sort(
            key=lambda r: (r.credibility_score * 0.6 + r.relevance_score * 0.4),
            reverse=True,
        )

        logger.info(
            f"News search '{keyword}': {len(all_results)} unique results"
        )
        return all_results[:top_k]

    def search_comparison(self, car1: str, car2: str) -> Dict:
        """Search for car comparison information via DuckDuckGo."""
        import re as _re
        query = f"{car1} vs {car2} 对比 价格 配置"
        raw = self._search_raw(query, max_results=10)
        if not raw:
            return {"car1": car1, "car2": car2, "results": [], "summary": "未找到对比信息"}

        scored = []
        for r in raw:
            if not isinstance(r, dict):
                continue
            url = r.get("link", r.get("url", ""))
            source = r.get("source", "DuckDuckGo")
            title = r.get("title", "")
            content = r.get("body", "") or r.get("snippet", "") or ""
            score, tier = self._score_source(url, source)
            scored.append({
                "title": title,
                "url": url,
                "content": content[:300],
                "source": source,
                "credibility_score": score,
                "credibility_tier": tier,
            })

        scored.sort(key=lambda r: r["credibility_score"], reverse=True)
        # Build a simple summary from top results
        summary_parts = [r["content"][:200] for r in scored[:3] if r["content"]]
        return {
            "car1": car1,
            "car2": car2,
            "results": scored[:5],
            "summary": "\n\n".join(summary_parts) if summary_parts else "未找到对比信息",
        }

    def extract_content(self, urls: List[str]) -> List[Dict]:
        """Extract full page content from URLs.

        DuckDuckGo doesn't support page extraction, returns empty list.
        For page extraction, consider using BeautifulSoup directly.
        """
        logger.debug(f"Page extraction not supported with DuckDuckGo ({len(urls)} URLs)")
        return []

    # ── Internal helpers ───────────────────────────────────

    def _search_single_dimension(
        self, query: str, dimension: str, weight: float
    ) -> List[SearchResult]:
        """Execute a single DDG search and wrap results."""
        raw_results = self._search_raw(query)
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("content", ""),
                source=r.get("source", ""),
                published_date=r.get("published_date", ""),
                dimension=dimension,
                relevance_score=r.get("score", 0.0) * weight if r.get("score") else weight * 50.0,
            )
            for r in raw_results
            if isinstance(r, dict) and r.get("content")
        ]

    def _search_raw(self, query: str, max_results: int = 10) -> List[Dict]:
        """Execute raw DuckDuckGo search."""
        if not duckduckgo_search.is_available:
            return []
        try:
            return duckduckgo_search._search_web(query, max_results=max_results)
        except Exception as exc:
            logger.warning(f"DDG raw search failed for '{query[:60]}': {exc}")
        return []

    @staticmethod
    def _extract_domain(url: str) -> str:
        """Extract the domain (netloc) from a URL, lowercased."""
        if not url:
            return ""
        try:
            parsed = urlparse(url)
            return (parsed.netloc or "").lower()
        except Exception:
            return ""

    def _score_source(self, url: str, source: str) -> Tuple[int, str]:
        """Score a source's credibility based on URL domain and source name.

        Only checks the domain portion of the URL, not the full path.
        """
        domain = self._extract_domain(url)
        source_lower = (source or "").lower()

        # 1) Check exact domain or source name matches
        for known, score in _CREDIBILITY_TIERS.items():
            if known in domain or known in source_lower:
                if score >= 90:
                    return score, "official"
                if score >= 70:
                    return score, "auto_platform"
                if score >= 50:
                    return score, "trusted_media"
                return score, "social_media"

        # 2) Check if domain belongs to an official brand (domain contains brand keyword)
        for brand_domain in _OFFICIAL_DOMAINS:
            if brand_domain in domain:
                return 90, "official"

        # 3) Check if it's a major auto platform
        for platform in _AUTO_PLATFORM_DOMAINS:
            if platform in domain:
                return 75, "auto_platform"

        # 4) Government / org / edu sites
        if any(domain.endswith(tld) for tld in [".gov.cn", ".org.cn", ".edu.cn"]):
            return 80, "official"

        # 5) Known news / media domains
        if any(kw in domain for kw in [
            "xinhua", "people", "cctv", "chinanews", "ce.cn", "yicai",
            "cls.cn", "caixin", "thepaper", "36kr", "geekpark",
        ]):
            return 60, "trusted_media"

        # 6) Domain looks like a news/media site
        if any(kw in domain for kw in ["news", "daily", "times", "post", "media", "press"]):
            return 55, "trusted_media"

        # 7) Source name contains news/media keywords
        if any(kw in source_lower for kw in ["新闻", "资讯", "日报", "时报", "财经", "汽车"]):
            return 45, "trusted_media"

        # Default: unknown source — still give a baseline, don't zero out
        return 30, "unknown"

    def _deduplicate(self, results: List[SearchResult]) -> List[SearchResult]:
        """Remove duplicate results by URL and near-duplicate content."""
        seen_urls: set = set()
        seen_hashes: set = set()
        unique: List[SearchResult] = []

        for r in results:
            # Exact URL dedup
            if r.url and r.url in seen_urls:
                continue
            # Near-duplicate content dedup (same hash prefix)
            h = r.content_hash
            if h in seen_hashes:
                continue

            seen_urls.add(r.url)
            seen_hashes.add(h)
            # Keep the result with higher credibility if dimension matches
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
        self, results: List[SearchResult], min_score: int = 20, min_content_len: int = 30
    ) -> List[SearchResult]:
        """Filter out low-quality results."""
        return [
            r
            for r in results
            if r.credibility_score >= min_score
            and len(r.content) >= min_content_len
            and not self._is_spam(r)
        ]

    def _is_spam(self, result: SearchResult) -> bool:
        """Detect obvious spam / low-quality content."""
        spam_patterns = [
            r"广告推广",
            r"点击购买",
            r"扫码咨询",
            r"加微信咨询",
            r"免费领取",
            r"限时抢购",
            r"一键拨号",
        ]
        text = result.title + result.content
        return any(re.search(p, text) for p in spam_patterns)


# ── Singleton ─────────────────────────────────────────────

web_search = WebSearchService()
