"""
Response formatter — pre-processes raw tool results into structured,
analyst-friendly content before feeding them into LLM prompts.

Transforms "database-export" style data into hierarchical, readable summaries
that the LLM can use to produce polished automotive-consultant responses.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from app.utils.helpers import format_price


class ResponseFormatter:
    """Formats raw tool payloads into structured, hierarchical content."""

    # ── Public API ────────────────────────────────────────────

    def format_for_intent(
        self,
        intent: str,
        payload: Any,
        car_info: dict = None,
    ) -> str:
        """Top-level dispatcher: format payload according to intent."""
        if intent == "car_price":
            return self.format_car_price(payload, car_info)
        if intent == "car_compare":
            return self.format_car_comparison(payload)
        if intent == "news":
            return self.format_news(payload)
        return self._fallback_format(payload)

    def format_car_price(self, payload: Any, car_info: dict = None) -> str:
        """Format car price search results into structured car-model content."""
        results = self._extract_results(payload)
        if not results:
            return self._no_data_message("车型价格数据", car_info)

        car_info = car_info or {}
        brand = car_info.get("brand", "") or results[0].get("brand", "")
        model = car_info.get("model", "") or results[0].get("model", "")

        lines = [f"## 数据概览：{brand} {model}", ""]

        # Group results by credibility tier
        by_tier = self._group_by_tier(results)
        lines.append(f"共获取 {len(results)} 条数据，来源分布：")
        for tier, count in by_tier.items():
            tier_name = {"official": "官方/厂商", "auto_platform": "汽车平台",
                         "trusted_media": "可信媒体", "social_media": "社交媒体",
                         "unknown": "其他来源", "local_kb": "本地知识库"}.get(tier, tier)
            lines.append(f"  - {tier_name}: {count} 条")
        lines.append("")

        # Version grouping — try to identify distinct versions
        versions = self._group_by_version(results)
        if versions:
            lines.append(f"## 版本信息（共识别 {len(versions)} 个版本）")
            lines.append("")
            for ver_name, ver_results in versions.items():
                lines.append(f"### {ver_name}")
                best = ver_results[0]
                price_str = format_price(best.get("price"), best.get("currency", "CNY")) if best.get("price") else "暂未查到"
                lines.append(f"- 参考价格: {price_str}")
                lines.append(f"- 来源: {best.get('source', '未知')} ({best.get('credibility_tier', 'unknown')})")
                if best.get("url"):
                    lines.append(f"- 链接: {best.get('url')}")
                if best.get("published_date"):
                    lines.append(f"- 发布时间: {best.get('published_date')}")
                # Include content snippet for LLM to extract specs
                content = best.get("content", "")
                if content:
                    lines.append(f"- 内容摘要: {content[:300]}")
                lines.append("")
        else:
            # No clear version grouping — list all results
            lines.append("## 搜索结果")
            lines.append("")
            for i, r in enumerate(results[:8], 1):
                price_str = format_price(r.get("price"), r.get("currency", "CNY")) if r.get("price") else "暂无"
                lines.append(f"### 结果 {i}: {r.get('title', '无标题')}")
                lines.append(f"- 参考价格: {price_str}")
                lines.append(f"- 来源: {r.get('source', '未知')} (可信度: {r.get('credibility_tier', 'unknown')})")
                content = r.get("content", "")
                if content:
                    lines.append(f"- 内容: {content[:300]}")
                if r.get("url"):
                    lines.append(f"- 链接: {r.get('url')}")
                lines.append("")

        lines.append("---")
        lines.append("提示: 以上为格式化后的搜索数据，请根据模板结构进行分析和回答。")
        lines.append("请从内容中提取电池容量、电机功率、续航里程、加速时间、智驾硬件等关键参数。")
        lines.append("缺失的数据请标注'暂未查到'，不要编造。")

        return "\n".join(lines)

    def format_car_comparison(self, payload: Any) -> str:
        """Format comparison results for the 8-section comparison template."""
        comparison_data = self._extract_comparison(payload)
        lines = ["## 对比原始数据", ""]

        cars = comparison_data.get("cars", [])
        car_labels = []
        for i, car in enumerate(cars):
            brand = car.get("brand", "?")
            model = car.get("model", "?")
            label = f"{brand} {model}".strip()
            car_labels.append(label)
            lines.append(f"### 车型 {i}: {label}")

            # Group fields by category for easier table population
            spec_groups = {
                "基础信息": ["brand", "model", "version", "price", "currency", "source", "credibility_tier"],
                "动力系统": ["drive_type", "motor_power", "horsepower", "acceleration", "top_speed"],
                "电池续航": ["battery_capacity", "battery_type", "range_km", "range_cltc", "charging_speed", "energy_type"],
                "智能驾驶": ["chip", "computing_power", "cameras", "radars", "lidar", "noa", "city_noa", "parking"],
                "车身空间": ["length", "width", "height", "wheelbase", "trunk_volume", "seats", "curb_weight"],
                "车机座舱": ["screen_size", "screen_count", "os", "voice_assistant", "hud"],
                "悬架底盘": ["suspension_front", "suspension_rear", "air_suspension", "chassis"],
            }

            for group_name, keys in spec_groups.items():
                found = False
                group_lines = []
                for key in keys:
                    val = car.get(key)
                    if val is not None and val != "" and val != 0:
                        found = True
                        if isinstance(val, float):
                            group_lines.append(f"  - {key}: {val:.2f}")
                        else:
                            group_lines.append(f"  - {key}: {val}")
                if found:
                    lines.append(f"**{group_name}**：")
                    lines.extend(group_lines)

            # Catch any remaining fields
            shown_keys = set()
            for group in spec_groups.values():
                shown_keys.update(group)
            shown_keys.update(("brand", "model"))
            remaining = {k: v for k, v in car.items() if k not in shown_keys and v}
            if remaining:
                lines.append("**其他信息**：")
                for k, v in remaining.items():
                    if isinstance(v, (int, float)):
                        lines.append(f"  - {k}: {v:.2f}")
                    elif isinstance(v, str) and len(v) < 200:
                        lines.append(f"  - {k}: {v}")
                    else:
                        lines.append(f"  - {k}: {str(v)[:200]}")

            lines.append("")

        # Add search content from cars for LLM to extract specs from
        lines.append("## 搜索内容片段（可从中提取参数信息）")
        lines.append("")
        for i, car in enumerate(cars):
            label = car_labels[i] if i < len(car_labels) else f"车型{i+1}"
            content_parts = []
            for field in ("content", "title", "url"):
                val = car.get(field)
                if isinstance(val, str) and val.strip():
                    content_parts.append(val.strip())
            if content_parts:
                combined = "\n".join(content_parts[:2])  # take up to 2 content fields
                lines.append(f"### {label}")
                lines.append(combined[:800])
                lines.append("")

        comparison_text = comparison_data.get("comparison", "")
        if comparison_text:
            lines.append("## 初步对比分析")
            lines.append(comparison_text)
            lines.append("")

        lines.append("---")
        lines.append(
            "请根据以上数据，按照对比模板的8段结构生成专业分析。"
            "参数对比表请用Markdown表格，尽可能填满每个参数行。"
            "缺失的参数标注'—'。"
            "内容片段中提及的电池容量、续航、加速、智驾芯片等关键参数，请提取到对比表中。"
        )
        return "\n".join(lines)

    def format_news(self, payload: Any) -> str:
        """Format news results."""
        news_list = self._extract_news_list(payload)
        if not news_list:
            return "暂无新闻数据。请诚实告知用户。"

        lines = [f"## 新闻数据（共 {len(news_list)} 条）", ""]
        for i, item in enumerate(news_list[:8], 1):
            lines.append(f"### 新闻 {i}: {item.get('title', '无标题')}")
            lines.append(f"- 来源: {item.get('source', '未知')}")
            if item.get("published_date"):
                lines.append(f"- 时间: {item.get('published_date')}")
            if item.get("credibility_tier"):
                lines.append(f"- 可信度: {item.get('credibility_tier')}")
            content = item.get("content", "")
            if content:
                lines.append(f"- 内容: {content[:400]}")
            if item.get("url"):
                lines.append(f"- 链接: {item.get('url')}")
            lines.append("")

        lines.append("---")
        lines.append("提示: 请选出1-2条最重要的作为头条，其余以速览形式呈现，并加入你的影响分析。")
        return "\n".join(lines)

    # ── Internal helpers ──────────────────────────────────────

    def _extract_results(self, payload: Any) -> List[Dict]:
        """Extract results list from various payload shapes."""
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("results", [])
        return []

    def _extract_comparison(self, payload: Any) -> Dict:
        if isinstance(payload, dict):
            return payload
        return {}

    def _extract_news_list(self, payload: Any) -> List[Dict]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("news_list", "results"):
                val = payload.get(key)
                if isinstance(val, list):
                    return val
        return []

    def _group_by_tier(self, results: List[Dict]) -> Dict[str, int]:
        groups = defaultdict(int)
        for r in results:
            tier = r.get("credibility_tier", "unknown")
            groups[tier] += 1
        return dict(groups)

    def _group_by_version(self, results: List[Dict]) -> Dict[str, List[Dict]]:
        """Group results by detected version string."""
        groups: Dict[str, List[Dict]] = {}
        for r in results:
            ver = r.get("version", "").strip()
            if not ver:
                # Try extracting from title
                title = r.get("title", "")
                import re
                m = re.search(r"(20\d{2}款|后轮驱动|长续航|高性能|标准版|四驱|旗舰|入门)", title)
                ver = m.group(1) if m else "未分类版本"
            if ver not in groups:
                groups[ver] = []
            groups[ver].append(r)

        # Sort groups — put groups with prices first
        def _sort_key(item):
            name, entries = item
            has_price = any(e.get("price") for e in entries)
            return (not has_price, name)
        return dict(sorted(groups.items(), key=_sort_key))

    def _no_data_message(self, data_type: str, car_info: dict = None) -> str:
        brand = (car_info or {}).get("brand", "")
        model = (car_info or {}).get("model", "")
        car_desc = f"{brand} {model}".strip() or "该车型"
        return f"未查询到{car_desc}的{data_type}。请诚实告知用户，并结合你的知识给出一般性建议。"

    def _fallback_format(self, payload: Any) -> str:
        if isinstance(payload, str):
            return payload
        if isinstance(payload, dict):
            lines = []
            for key, value in payload.items():
                if isinstance(value, (list, dict)):
                    continue
                lines.append(f"- {key}: {value}")
            return "\n".join(lines) if lines else str(payload)
        return str(payload)


formatter = ResponseFormatter()
