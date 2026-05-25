"""
Answer planner — selects the right template and builds a structured plan
for the LLM to follow when generating the final response.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from app.agent.templates import AnswerTemplate, get as get_template
from app.core.logging import logger


class AnswerStyle(str, Enum):
    """Broad answer styles that map to templates."""
    CAR_MODEL = "car_model"
    PRICE_TREND = "price_trend"
    COMPARISON = "comparison"
    NEWS = "news"
    GENERAL = "general"


# ── Style selection hints ────────────────────────────────────

_STYLE_HINTS = {
    AnswerStyle.CAR_MODEL: [
        "版本", "配置", "参数", "续航", "电池", "电机", "驱动",
        "智驾", "芯片", "雷达", "摄像头", "算力", "车型", "全系",
        "哪个版本", "有什么版本", "在售", "新款", "改款",
    ],
    AnswerStyle.PRICE_TREND: [
        "降价", "涨价", "优惠", "促销", "行情", "走势",
        "什么时候买", "值得入手", "划算", "落地价", "裸车价",
        "折扣", "补贴", "置换", "金融", "贷款",
    ],
    AnswerStyle.COMPARISON: [
        "对比", "比较", "哪个好", "区别", "差异", "vs",
        "选哪个", "推荐哪个", "二选一", "怎么选",
    ],
    AnswerStyle.NEWS: [
        "新闻", "资讯", "动态", "消息", "发布会", "热点",
        "最新", "行业", "政策",
    ],
}


@dataclass
class AnswerPlan:
    """A structured plan for generating the final answer."""
    style: AnswerStyle
    template: Optional[AnswerTemplate] = None
    sections: List[str] = field(default_factory=list)
    data_hints: List[str] = field(default_factory=list)
    special_notes: List[str] = field(default_factory=list)

    @property
    def has_template(self) -> bool:
        return self.template is not None


class AnswerPlanner:
    """Selects answer style and builds a generation plan from user intent and message."""

    def plan(
        self,
        intent: str,
        message: str,
        has_multiple_cars: bool = False,
        has_price_data: bool = False,
        has_trend_data: bool = False,
    ) -> AnswerPlan:
        style = self._determine_style(intent, message, has_multiple_cars,
                                      has_price_data, has_trend_data)
        template = get_template(style.value) if style != AnswerStyle.GENERAL else None

        plan = AnswerPlan(style=style, template=template)

        if template:
            plan.sections = [title for title, _ in template.sections]

        plan.data_hints = self._build_data_hints(style, has_price_data)
        plan.special_notes = self._build_special_notes(style, message)

        logger.info(
            f"Answer plan: style={style.value}, "
            f"template={template.name if template else 'none'}, "
            f"sections={len(plan.sections)}"
        )
        return plan

    def _determine_style(
        self,
        intent: str,
        message: str,
        has_multiple_cars: bool,
        has_price_data: bool,
        has_trend_data: bool,
    ) -> AnswerStyle:
        message_lower = message.lower()

        if intent == "car_compare" or has_multiple_cars:
            return AnswerStyle.COMPARISON
        if intent == "news":
            return AnswerStyle.NEWS

        if intent == "car_price":
            if has_trend_data or any(hint in message_lower for hint in _STYLE_HINTS[AnswerStyle.PRICE_TREND]):
                return AnswerStyle.PRICE_TREND
            if any(hint in message_lower for hint in _STYLE_HINTS[AnswerStyle.CAR_MODEL]):
                return AnswerStyle.CAR_MODEL
            if has_price_data:
                return AnswerStyle.CAR_MODEL
            return AnswerStyle.CAR_MODEL

        # GENERAL intent — check if message still hints at car model questions
        for hint in _STYLE_HINTS[AnswerStyle.CAR_MODEL]:
            if hint in message_lower:
                return AnswerStyle.CAR_MODEL
        for hint in _STYLE_HINTS[AnswerStyle.COMPARISON]:
            if hint in message_lower:
                return AnswerStyle.COMPARISON

        return AnswerStyle.GENERAL

    def _build_data_hints(self, style: AnswerStyle, has_price: bool) -> List[str]:
        hints = []
        if not has_price:
            hints.append("本次搜索未获取到完整价格数据，请诚实说明并在参数表中标注'暂未查到'")
        if style == AnswerStyle.CAR_MODEL:
            hints.append("如果有多个版本，请确保每个版本的核心参数都被列出")
            hints.append("优先整理官方/经销商渠道价格，其次才是第三方平台")
        if style == AnswerStyle.COMPARISON:
            hints.append("每个对比维度必须同时出现双方数据")
        return hints

    def _build_special_notes(self, style: AnswerStyle, message: str) -> List[str]:
        notes = []
        if style == AnswerStyle.CAR_MODEL:
            notes.append("如果发现搜索结果中有新增/改款版本，请在总览中突出标注")
        if style == AnswerStyle.PRICE_TREND:
            notes.append("请明确给出购买时机的判断（现在买/再等等/不着急）")
        if style == AnswerStyle.GENERAL:
            notes.append("即使是通用对话，也请保持汽车领域的专业口吻")
        return notes


planner = AnswerPlanner()
