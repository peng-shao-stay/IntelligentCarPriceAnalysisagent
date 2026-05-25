"""
Validator Agent — 结果去重、来源验证、质量检查
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from app.multi_agent.base import AgentResult, BaseAgent
from app.core.logging import logger


class ValidatorAgent(BaseAgent):
    """验证 Agent：去重、来源验证、质量检查。"""

    name = "validator"

    def dedup(self, results: List[Dict]) -> AgentResult:
        """基于 URL 和内容去重。"""
        seen_urls = set()
        seen_hashes = set()
        deduped = []

        for item in results:
            url = item.get("url", "") or item.get("source_url", "")
            content = item.get("content", "") or item.get("body", "") or ""
            content_hash = hashlib_md5(content[:200])

            if url and url in seen_urls:
                continue
            if not url and content_hash in seen_hashes:
                continue

            if url:
                seen_urls.add(url)
            seen_hashes.add(content_hash)
            deduped.append(item)

        removed = len(results) - len(deduped)
        if removed:
            logger.info(f"Validator: dedup removed {removed} duplicates")
        return AgentResult.ok({"items": deduped, "removed": removed})

    def filter_low_quality(self, results: List[Dict], min_score: int = 30) -> AgentResult:
        """过滤低可信度结果。"""
        filtered = []
        for item in results:
            score = item.get("credibility_score", 50)
            if isinstance(score, (int, float)) and score >= min_score:
                filtered.append(item)
            else:
                content = (item.get("content", "") or "")[:100]
                logger.info(f"Validator: filtered low-score ({score}) item: {content[:50]}...")
        return AgentResult.ok({"items": filtered, "removed": len(results) - len(filtered)})

    def validate_urls(self, results: List[Dict]) -> AgentResult:
        """验证 URL 是否有效。"""
        valid = []
        for item in results:
            url = item.get("url", "") or item.get("source_url", "")
            if url and re.match(r"^https?://", url):
                valid.append(item)
            elif not url:
                item["url"] = ""
                valid.append(item)
        return AgentResult.ok({"items": valid})

    def quality_report(self, results: List[Dict]) -> AgentResult:
        """生成数据质量报告。"""
        total = len(results)
        with_price = sum(1 for r in results if r.get("price") is not None)
        with_url = sum(1 for r in results if r.get("url"))
        with_content = sum(1 for r in results if r.get("content"))
        avg_score = sum(
            r.get("credibility_score", 50) for r in results
        ) / max(total, 1)

        return AgentResult.ok({
            "total": total,
            "with_price": with_price,
            "with_url": with_url,
            "with_content": with_content,
            "avg_credibility": round(avg_score, 1),
            "quality": "high" if avg_score >= 70 else "medium" if avg_score >= 40 else "low",
        })


def hashlib_md5(text: str) -> str:
    import hashlib
    return hashlib.md5(text.encode()).hexdigest()
