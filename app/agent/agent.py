"""
Core agent runtime — automotive sales consultant edition.

Pipeline:
  User message
  → Intent detection (keyword matching)
  → Tool execution via Provider layer
  → AnswerPlanner selects template
  → ResponseFormatter pre-processes raw data
  → Template-aware prompt guides LLM
  → LLM generates polished, analyst-quality response

Dependencies:
  - SearchProvider  – web search (prices, news, comparisons)
  - VectorProvider  – semantic / RAG search
  - DatabaseProvider – session management
  All injected via ProviderRegistry; no direct search / RAG imports.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Dict, List, Optional

_request_local = threading.local()

from app.agent.context import (
    build_conversation_messages,
    summarize_history,
)
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
from app.agent.tool_registry import AgentTool, ToolExecutionResult, ToolRegistry
from app.agent.tools.compare import compare_cars
from app.agent.tools.news_search import summarize_news
from app.core.logging import logger
from app.providers.registry import ProviderRegistry, get_provider_registry
from app.services.llm_service import llm_service
from app.utils.helpers import (
    extract_car_info,
    extract_multiple_car_info,
    extract_news_keyword,
    format_price,
)


class Intent(str, Enum):
    CAR_PRICE = "car_price"
    CAR_COMPARE = "car_compare"
    NEWS = "news"
    GENERAL = "general"


_MISSING_CAR_INFO_MSG = "我还没识别出完整的品牌和车型。你可以试试「特斯拉 Model 3 多少钱」。"


# Map intent to its response prompt template
_INTENT_PROMPT_MAP = {
    "car_model": CAR_MODEL_RESPONSE_PROMPT,
    "price_trend": PRICE_TREND_RESPONSE_PROMPT,
    "comparison": COMPARISON_RESPONSE_PROMPT,
    "news": NEWS_RESPONSE_PROMPT,
}


class AutoMindAgent:
    """Automotive AI agent with structured answer generation pipeline.

    All external tool dependencies are accessed through ProviderRegistry:
      - self.providers.search   → SearchProvider   (web search)
      - self.providers.vector   → VectorProvider   (RAG / semantic search)
      - self.providers.database → DatabaseProvider (DB sessions)
    """

    def __init__(
        self,
        llm_client=None,
        tool_registry: ToolRegistry = None,
        max_steps: int = 3,
        providers: ProviderRegistry = None,
    ):
        self.llm_service = llm_client or llm_service
        self.max_steps = max_steps
        self.providers = providers or get_provider_registry()
        self.tool_registry = tool_registry or self._build_tool_registry()
        self.system_prompt = self._build_system_prompt()

        logger.info(
            f"AutoMind agent initialized | "
            f"tools: {self.tool_registry.tool_count}"
        )

    def _build_system_prompt(self) -> str:
        """Build the system prompt with tool descriptions."""
        tools_section = self._build_tools_prompt_section()
        return build_dynamic_system_prompt(tools_section)

    def _build_tools_prompt_section(self) -> str:
        """Generate the 'Available Tools' section for the system prompt."""
        tools = self.tool_registry.list_tools()
        if not tools:
            return ""

        lines = [
            "## 可用工具",
            "",
            "你可以使用以下工具来回答用户的问题：",
            "",
        ]

        for t in tools:
            lines.append(f"- **{t.name}**: {t.description}")
        lines.append("")
        lines.append("使用规则：")
        lines.append("1. 根据用户问题选择最合适的工具")
        lines.append("2. 一次只使用一个工具，不要同时调用多个")

        return "\n".join(lines)

    def _build_tool_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(
            AgentTool(
                name="car_price",
                description="Query the latest car prices and specs",
                intent=Intent.CAR_PRICE,
                handler=self._run_car_price_tool,
            )
        )
        registry.register(
            AgentTool(
                name="car_compare",
                description="Compare multiple cars",
                intent=Intent.CAR_COMPARE,
                handler=self._run_car_comparison_tool,
            )
        )
        registry.register(
            AgentTool(
                name="news",
                description="Search recent automotive news",
                intent=Intent.NEWS,
                handler=self._run_news_tool,
            )
        )
        return registry

    # ── Main entry ────────────────────────────────────────────

    def process_message(self, message: str, history: List[Dict] = None, web_search: bool = False, db=None) -> str:
        """Process a user message using the multi-agent orchestration pipeline."""
        history = history or []
        _request_local.web_search_enabled = web_search

        try:
            intent = self._detect_intent(message)

            # Early: CAR_PRICE with missing brand/model → ask for clarification
            if intent == Intent.CAR_PRICE:
                car_info = extract_car_info(message)
                if not car_info.get("brand") or not car_info.get("model"):
                    return _MISSING_CAR_INFO_MSG

            # Use OrchestratorAgent pipeline when LLM is available
            if getattr(self.llm_service, "is_available", False):
                from app.multi_agent.orchestrator import OrchestratorAgent
                orchestrator = OrchestratorAgent(
                    llm_service=self.llm_service,
                    providers=self.providers,
                    tool_registry=self.tool_registry,
                )
                return orchestrator.process(
                    message=message,
                    history=history,
                    web_search=web_search,
                    db=db,
                )

            # Fallback: direct tool execution (no LLM)
            tool = self.tool_registry.get_by_intent(intent)
            if tool is not None:
                tool_result = self.tool_registry.execute(intent, message, history)
                if not tool_result.success:
                    return tool_result.summary
                return self._respond_with_template(
                    message=message,
                    history=history,
                    intent=intent.value,
                    payload=tool_result.payload,
                )

            return self._handle_general_chat(message, history)

        except Exception:
            logger.exception("Error processing message")
            return "抱歉，处理你的请求时出现了一些问题，请稍后再试。"

    # ── Intent detection ──────────────────────────────────────

    def _detect_intent(self, message: str) -> Intent:
        """Detect user intent with keyword matching."""
        message_lower = message.lower()

        price_keywords = ["价格", "多少钱", "报价", "售价", "落地价", "优惠", "降价", "涨价", "行情", "走势", "裸车", "成交价"]
        compare_keywords = ["对比", "比较", "哪个好", "区别", "差异", "vs"]
        news_keywords = ["新闻", "资讯", "动态", "消息", "发布会", "热点"]

        if any(keyword in message_lower for keyword in price_keywords):
            return Intent.CAR_PRICE
        if any(keyword in message_lower for keyword in compare_keywords):
            return Intent.CAR_COMPARE
        if any(keyword in message_lower for keyword in news_keywords):
            return Intent.NEWS

        return Intent.GENERAL

    # ── Tool handlers ─────────────────────────────────────────

    def _run_car_price_tool(self, message: str, history: Optional[List[Dict]] = None) -> ToolExecutionResult:
        car_info = extract_car_info(message)
        brand = car_info.get("brand")
        model = car_info.get("model")

        if not brand or not model:
            return ToolExecutionResult(
                tool_name="car_price",
                success=False,
                payload=car_info,
                summary="我还没识别出完整的品牌和车型。你可以试试「特斯拉 Model 3 多少钱」。",
            )

        results: List[Dict] = []
        if getattr(_request_local, 'web_search_enabled', False):
            results = self.providers.search.search_car_price(
                brand=brand, model=model, version=car_info.get("version")
            )
        else:
            try:
                db = self.providers.database.create_session()
                try:
                    rag_results = self.providers.vector.search(
                        db, f"{brand} {model} {car_info.get('version', '')} 价格",
                        top_k=5
                    )
                finally:
                    self.providers.database.close_session(db)
                if rag_results:
                    for r in rag_results:
                        results.append({
                            "brand": r.get("brand") or brand,
                            "model": r.get("model") or model,
                            "version": r.get("year", ""),
                            "price": None,
                            "currency": "CNY",
                            "trend": "stable",
                            "title": r.get("title", ""),
                            "url": r.get("source_url", ""),
                            "content": r.get("content", ""),
                            "source": "本地知识库",
                            "credibility_score": 90,
                            "credibility_tier": "local_kb",
                            "dimension": "rag",
                            "published_date": r.get("publish_time", ""),
                        })
            except Exception as exc:
                logger.warning(f"RAG fallback failed: {exc}")

        if not results:
            mode_hint = "联网搜索已关闭，" if not getattr(_request_local, 'web_search_enabled', False) else ""
            return ToolExecutionResult(
                tool_name="car_price",
                success=False,
                payload=car_info,
                summary=f"{mode_hint}暂时没有查到 {brand} {model} 的最新价格数据。你可以稍后再试，或补充更具体的版本信息。",
            )

        return ToolExecutionResult(
            tool_name="car_price",
            success=True,
            payload={"car_info": car_info, "results": results},
            summary="",
        )

    def _run_car_comparison_tool(
        self,
        message: str,
        history: Optional[List[Dict]] = None,
    ) -> ToolExecutionResult:
        cars = extract_multiple_car_info(message)
        if len(cars) < 2:
            return ToolExecutionResult(
                tool_name="car_compare",
                success=False,
                payload=cars,
                summary="我至少需要两款车才能做对比。你可以试试，对比一下比亚迪汉和特斯拉 Model 3",
            )

        def _enrich_car(car):
            enriched = dict(car)
            brand = car.get("brand")
            model = car.get("model")
            if brand and model:
                results = self.providers.search.search_car_price(
                    brand=brand, model=model, version=car.get("version")
                )
                if results:
                    enriched.update(results[0])
            return enriched

        with ThreadPoolExecutor(max_workers=min(len(cars), 4)) as pool:
            enriched_cars = list(pool.map(_enrich_car, cars))

        comparison_result = compare_cars(enriched_cars, llm_client=self.llm_service
                                          if getattr(self.llm_service, "is_available", False) else None)
        return ToolExecutionResult(
            tool_name="car_compare",
            success=True,
            payload={"cars": enriched_cars, "comparison": comparison_result},
            summary=comparison_result,
        )

    def _run_news_tool(self, message: str, history: Optional[List[Dict]] = None) -> ToolExecutionResult:
        car_info = extract_car_info(message)
        brand = car_info.get("brand")
        keyword = extract_news_keyword(message)

        if not getattr(_request_local, 'web_search_enabled', False):
            return ToolExecutionResult(
                tool_name="news",
                success=False,
                payload={"keyword": keyword},
                summary=f"联网搜索已关闭。关于「{keyword}」的新闻资讯需要联网获取，请打开联网搜索开关后重试。",
            )

        news_list = self.providers.search.search_news(keyword, limit=5)
        if not news_list and brand:
            news_list = self.providers.search.search_news(brand, limit=5)

        if not news_list:
            return ToolExecutionResult(
                tool_name="news",
                success=False,
                payload={"keyword": keyword},
                summary=f"暂时没有查到和「{keyword}」相关的新闻。",
            )

        llm_client = self.llm_service if getattr(self.llm_service, "is_available", False) else None
        summary = summarize_news(news_list, llm_client=llm_client)
        return ToolExecutionResult(
            tool_name="news",
            success=True,
            payload={"keyword": keyword, "news_list": news_list, "summary": summary},
            summary=summary,
        )

    # ── Template-based response generation ───────────────────

    def _respond_with_template(
        self,
        message: str,
        history: List[Dict],
        intent: str,
        payload,
    ) -> str:
        """Generate response using the planner → formatter → template prompt pipeline."""
        if not getattr(self.llm_service, "is_available", False):
            if isinstance(payload, dict):
                for key in ("summary", "comparison"):
                    val = payload.get(key)
                    if isinstance(val, str) and val.strip():
                        return val
            return "已获取到相关数据，但当前没有可用的 LLM 来生成回答。"

        car_info = payload.get("car_info", {}) if isinstance(payload, dict) else {}
        results = payload.get("results", []) if isinstance(payload, dict) else []
        has_price = any(r.get("price") for r in results if isinstance(r, dict))
        has_trend = any(
            r.get("trend") in ("up", "down") for r in results if isinstance(r, dict)
        )
        has_multiple = len(car_info.get("model", "").split()) < 2 and len(results) > 3

        plan = planner.plan(
            intent=intent,
            message=message,
            has_multiple_cars=(intent == "car_compare") or has_multiple,
            has_price_data=has_price,
            has_trend_data=has_trend,
        )

        formatted_data = formatter.format_for_intent(intent, payload, car_info)
        prompt = self._build_template_prompt(
            plan=plan,
            formatted_data=formatted_data,
            message=message,
            history=history,
        )

        try:
            return self.llm_service.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=self.system_prompt,
            )
        except Exception as exc:
            logger.warning(f"LLM template response failed: {exc}")
            return self._build_fallback_response(intent, payload, car_info)

    def _build_template_prompt(
        self,
        plan,
        formatted_data: str,
        message: str,
        history: List[Dict],
    ) -> str:
        """Build a template-aware prompt with all sections populated."""
        template = plan.template

        prompt_template = _INTENT_PROMPT_MAP.get(plan.style.value)
        if prompt_template is None:
            return GENERAL_CHAT_PROMPT.format(
                conversation_summary=summarize_history(history),
                user_message=message,
            )

        kwargs = {
            "formatted_data": formatted_data,
            "conversation_summary": summarize_history(history),
            "user_message": message,
            "data_hints": "\n".join(f"- {h}" for h in plan.data_hints) if plan.data_hints else "无特殊提示",
            "special_notes": "\n".join(f"- {n}" for n in plan.special_notes) if plan.special_notes else "无",
        }

        if template:
            for i, (title, _instructions) in enumerate(template.sections):
                kwargs[f"section_{i}"] = title
            for i in range(len(template.sections), 5):
                kwargs[f"section_{i}"] = "（无）"
            kwargs["style_rules"] = "\n".join(f"- {r}" for r in template.style_rules)
            kwargs["forbidden_patterns"] = "\n".join(f"- {p}" for p in template.forbidden_patterns)
        else:
            for i in range(5):
                kwargs[f"section_{i}"] = "（无）"
            kwargs["style_rules"] = "保持专业、简洁的风格"
            kwargs["forbidden_patterns"] = "禁止输出 JSON 格式"

        return prompt_template.format(**kwargs)

    def _build_fallback_response(self, intent: str, payload, car_info: dict) -> str:
        """Generate a simple fallback when LLM is unavailable."""
        if intent == "car_price":
            brand = car_info.get("brand", "")
            model = car_info.get("model", "")
            results = payload.get("results", []) if isinstance(payload, dict) else []
            if results:
                with_price = [r for r in results if r.get("price")]
                if with_price:
                    best = with_price[0]
                    price_str = format_price(best.get("price"), best.get("currency", "CNY"))
                    return (
                        f"{brand} {model} 参考价格为 {price_str}，"
                        f"数据来源：{best.get('source', '未知')}。"
                        f"共获取 {len(results)} 条相关信息。"
                        f"建议开启联网搜索获取更详细的版本分析。"
                    )
            return f"已获取 {brand} {model} 的相关数据，但当前无法生成详细分析。请稍后重试。"

        if intent == "car_compare":
            return payload.get("comparison", "已获取对比数据，但当前无法生成详细分析。")

        if intent == "news":
            return payload.get("summary", "已获取新闻数据，但当前无法生成详细分析。")

        return "已获取相关数据，但当前无法生成详细分析。请稍后重试。"

    # ── General chat ──────────────────────────────────────────

    def _handle_general_chat(self, message: str, history: List[Dict] = None) -> str:
        if not getattr(self.llm_service, "is_available", False):
            return "我目前没有可用的 LLM 配置。请先配置 API_KEY 或本地 Ollama，再继续通用对话。"

        web_search_enabled = getattr(_request_local, 'web_search_enabled', False)

        search_results_text = ""
        if web_search_enabled:
            try:
                search_results = self.providers.search.search_general(message, max_results=5)
                if search_results:
                    parts = []
                    for i, r in enumerate(search_results, 1):
                        parts.append(
                            f"[{i}] {r['title']}\n"
                            f"来源: {r.get('source', '未知')} | {r.get('published_date', '')}\n"
                            f"链接: {r.get('url', '')}\n"
                            f"内容: {r['content']}\n"
                        )
                    search_results_text = "\n".join(parts)
                    logger.info(f"General chat with web search: {len(search_results)} results")
            except Exception as exc:
                logger.warning(f"Web search for general chat failed: {exc}")

        if search_results_text:
            prompt = GENERAL_CHAT_WITH_SEARCH_PROMPT.format(
                conversation_summary=summarize_history(history),
                search_results=search_results_text,
                user_message=message,
            )
        else:
            prompt = GENERAL_CHAT_PROMPT.format(
                conversation_summary=summarize_history(history),
                user_message=message,
            )

        messages = build_conversation_messages(history, message)
        if messages:
            messages[-1] = {"role": "user", "content": prompt}
        else:
            messages = [{"role": "user", "content": prompt}]

        return self.llm_service.chat(messages=messages, system_prompt=self.system_prompt)


# ═══════════════════════════════════════════════════════════════
#  Module-level agent singleton
# ═══════════════════════════════════════════════════════════════

agent: Optional[AutoMindAgent] = None


def get_agent() -> AutoMindAgent:
    """Get the current agent singleton."""
    global agent
    if agent is None:
        agent = AutoMindAgent()
    return agent
