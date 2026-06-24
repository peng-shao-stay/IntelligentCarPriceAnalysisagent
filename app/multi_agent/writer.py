"""
Writer Agent — 结构化 MD 报告生成
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.multi_agent.base import AgentResult, BaseAgent
from app.agent.formatter import formatter
from app.agent.planner import planner
from app.agent.prompts import (
    CAR_MODEL_RESPONSE_PROMPT,
    COMPARISON_RESPONSE_PROMPT,
    GENERAL_CHAT_PROMPT,
    GENERAL_CHAT_WITH_SEARCH_PROMPT,
    NEWS_RESPONSE_PROMPT,
    PRICE_TREND_RESPONSE_PROMPT,
    SYSTEM_PROMPT,
    build_dynamic_system_prompt,
)
from app.core.logging import logger


class WriterAgent(BaseAgent):
    """Writer Agent：用模板生成专业 MD 格式报告。"""

    name = "writer"

    # ── 主入口 ─────────────────────────────────────────────────

    def generate_report(
        self,
        intent: str,
        message: str,
        search_data: List[Dict] = None,
        knowledge_data: List[Dict] = None,
        history: List[Dict] = None,
    ) -> AgentResult:
        """生成 MD 报告：合并搜索 + 知识库数据 → 模板 → LLM 生成。"""
        history = history or []
        search_data = search_data or []
        knowledge_data = knowledge_data or []

        # 合并数据源
        all_results = self._merge_sources(search_data, knowledge_data)

        if not all_results:
            return AgentResult.fail("无可用数据生成报告")

        # 分析数据特征
        has_price = any(r.get("price") for r in all_results if isinstance(r, dict))
        has_trend = any(
            r.get("trend") in ("up", "down") for r in all_results if isinstance(r, dict)
        )

        # Planner 选择模板
        plan = planner.plan(
            intent=intent, message=message,
            has_multiple_cars=(intent == "car_compare") or len(all_results) > 3,
            has_price_data=has_price, has_trend_data=has_trend,
        )

        # Formatter 预处理
        payload = {"results": all_results, "car_info": self._extract_car_info(all_results)}
        formatted = formatter.format_for_intent(intent, payload, payload["car_info"])

        # 构建 prompt
        prompt = self._build_prompt(plan, formatted, message, history)

        # LLM 生成
        if not self.llm_service or not getattr(self.llm_service, "is_available", False):
            return AgentResult.fail("LLM 不可用，无法生成报告")

        try:
            report = self.llm_service.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=SYSTEM_PROMPT,
            )
            logger.info(f"Writer: generated {len(report)} chars MD report for intent={intent}")
            return AgentResult.ok({
                "report": report,
                "style": plan.style.value,
                "sections": plan.sections,
                "source_count": len(all_results),
                "has_price": has_price,
            })
        except Exception as exc:
            logger.warning(f"Writer LLM failed: {exc}")
            return AgentResult.fail(f"报告生成失败: {exc}")

    def generate_general_chat(
        self, message: str, history: List[Dict] = None,
        search_results: str = "",
    ) -> AgentResult:
        """生成通用对话回复。"""
        history = history or []
        from app.agent.context import summarize_history

        if search_results:
            prompt = GENERAL_CHAT_WITH_SEARCH_PROMPT.format(
                conversation_summary=summarize_history(history),
                search_results=search_results,
                user_message=message,
            )
        else:
            prompt = GENERAL_CHAT_PROMPT.format(
                conversation_summary=summarize_history(history),
                user_message=message,
            )

        if not self.llm_service or not getattr(self.llm_service, "is_available", False):
            return AgentResult.fail("LLM 不可用")

        try:
            response = self.llm_service.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=SYSTEM_PROMPT,
            )
            return AgentResult.ok({"report": response})
        except Exception as exc:
            logger.warning(f"Writer general chat failed: {exc}")
            return AgentResult.fail(f"对话生成失败: {exc}")

    # ── 内部方法 ──────────────────────────────────────────────

    def _merge_sources(
        self, search_data: List[Dict], knowledge_data: List[Dict]
    ) -> List[Dict]:
        """合并去重搜索和知识库结果。"""
        seen_urls = set()
        merged = []
        for item in search_data + knowledge_data:
            url = item.get("url", item.get("source_url", ""))
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            merged.append(item)
        return merged

    def _extract_car_info(self, results: List[Dict]) -> Dict:
        """从结果集中提取品牌/车型信息。"""
        for r in results:
            brand = r.get("brand") or r.get("brand_name", "")
            model = r.get("model") or r.get("model_name", "")
            if brand and model:
                return {"brand": brand, "model": model, "version": r.get("version", "")}
        return {"brand": "", "model": "", "version": ""}

    def _build_prompt(self, plan, formatted: str, message: str, history: List[Dict]) -> str:
        """构建模板 prompt。"""
        from app.agent.context import summarize_history
        from app.agent.agent import _INTENT_PROMPT_MAP

        prompt_template = _INTENT_PROMPT_MAP.get(plan.style.value)
        if prompt_template is None:
            return GENERAL_CHAT_PROMPT.format(
                conversation_summary=summarize_history(history),
                user_message=message,
            )

        kwargs = {
            "formatted_data": formatted,
            "conversation_summary": summarize_history(history),
            "user_message": message,
            "data_hints": "\n".join(f"- {h}" for h in plan.data_hints) if plan.data_hints else "无特殊提示",
            "special_notes": "\n".join(f"- {n}" for n in plan.special_notes) if plan.special_notes else "无",
        }
        if plan.template:
            for i, (title, _) in enumerate(plan.template.sections):
                kwargs[f"section_{i}"] = title
            for i in range(len(plan.template.sections), 5):
                kwargs[f"section_{i}"] = "（无）"
            kwargs["style_rules"] = "\n".join(f"- {r}" for r in plan.template.style_rules)
            kwargs["forbidden_patterns"] = "\n".join(f"- {p}" for p in plan.template.forbidden_patterns)
        else:
            for i in range(5):
                kwargs[f"section_{i}"] = "（无）"
            kwargs["style_rules"] = "保持专业、简洁的风格"
            kwargs["forbidden_patterns"] = "禁止输出 JSON 格式"

        return prompt_template.format(**kwargs)
