"""
Orchestrator Agent — 编排多 Agent 管道
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.multi_agent.base import AgentResult, BaseAgent
from app.multi_agent.searcher import SearcherAgent
from app.multi_agent.knowledge import KnowledgeAgent
from app.multi_agent.writer import WriterAgent
from app.multi_agent.validator import ValidatorAgent
from app.agent.tool_registry import ToolRegistry
from app.core.logging import logger
from app.utils.helpers import extract_car_info, extract_multiple_car_info, extract_news_keyword


class OrchestratorAgent(BaseAgent):
    """编排 Agent：协调 Searcher / Knowledge / Writer / Validator 完成用户请求。

    管道流程:
      用户消息 → Intent 检测
        → Searcher + Knowledge (并行)
        → Validator 去重过滤
        → Writer 生成 MD 报告
        → 返回
    """

    name = "orchestrator"

    def __init__(self, llm_service=None, providers=None, tool_registry: ToolRegistry = None):
        super().__init__(llm_service, providers)
        self.tool_registry = tool_registry
        # 子 Agent
        self.searcher = SearcherAgent(llm_service, providers)
        self.knowledge = KnowledgeAgent(llm_service, providers)
        self.writer = WriterAgent(llm_service, providers)
        self.validator = ValidatorAgent(llm_service, providers)

    def process(
        self,
        message: str,
        history: List[Dict] = None,
        web_search: bool = False,
        db: Session = None,
    ) -> str:
        """处理用户消息的主入口。"""
        history = history or []
        from app.agent.agent import Intent

        # Step 1: Intent 检测
        intent = self._detect_intent(message)

        if intent == Intent.GENERAL:
            return self._handle_general(message, history, web_search)

        # Step 2: 提取关键信息
        car_info = extract_car_info(message)
        brand, model = car_info.get("brand", ""), car_info.get("model", "")

        # Step 3: 并行搜索 + 知识库检索
        search_data, knowledge_data = [], []
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = []

            # 搜索任务
            if web_search:
                futures.append(pool.submit(
                    self._search_by_intent, intent, message, brand, model
                ))

            # 知识库任务
            if db and (brand or model):
                futures.append(pool.submit(
                    self._knowledge_search, db, message, brand, model
                ))

            for future in futures:
                result = future.result()
                if result:
                    if isinstance(result, list):
                        search_data.extend(result)
                    elif isinstance(result, dict):
                        search_data.append(result)

        # Step 4: 知识库单独查询
        knowledge_results = []
        if db:
            kb_result = self.knowledge.search(db, message)
            if kb_result:
                knowledge_results = kb_result.data if isinstance(kb_result.data, list) else []

        # Step 5: Validator 去重
        all_results = search_data + knowledge_results
        deduped = self.validator.dedup(all_results)
        if deduped:
            filtered = self.validator.filter_low_quality(deduped.data.get("items", all_results))
            clean_results = filtered.data.get("items", all_results) if filtered else all_results
        else:
            clean_results = all_results

        # Step 6: Writer 生成 MD 报告
        writer_result = self.writer.generate_report(
            intent=intent.value, message=message,
            search_data=clean_results, knowledge_data=[],
            history=history,
        )
        if writer_result:
            return writer_result.data.get("report", "")

        # Fallback
        if clean_results:
            return self._fallback_text(intent, clean_results, car_info)
        return "抱歉，暂时没有查到相关信息。"

    def _detect_intent(self, message: str):
        from app.agent.agent import Intent
        msg = message.lower()
        price_kw = ["价格", "多少钱", "报价", "售价", "落地价", "优惠", "降价", "行情", "裸车"]
        compare_kw = ["对比", "比较", "哪个好", "区别", "差异", "vs"]
        news_kw = ["新闻", "资讯", "动态", "消息", "发布会", "热点"]

        if any(k in msg for k in price_kw):
            return Intent.CAR_PRICE
        if any(k in msg for k in compare_kw):
            return Intent.CAR_COMPARE
        if any(k in msg for k in news_kw):
            return Intent.NEWS
        return Intent.GENERAL

    def _search_by_intent(self, intent, message: str, brand: str, model: str) -> list:
        from app.agent.agent import Intent
        if intent == Intent.CAR_PRICE and brand and model:
            r = self.searcher.search_car_price(brand, model)
            return r.data if r else []
        if intent == Intent.NEWS:
            kw = extract_news_keyword(message) or brand or "汽车"
            r = self.searcher.search_news(kw)
            return r.data if r else []
        if intent == Intent.CAR_COMPARE:
            cars = extract_multiple_car_info(message)
            if len(cars) >= 2:
                all_results = []
                for c in cars[:2]:
                    r = self.searcher.search_car_price(c.get("brand", ""), c.get("model", ""))
                    if r:
                        all_results.extend(r.data if isinstance(r.data, list) else [])
                return all_results
        # General search
        r = self.searcher.search_general(message)
        return r.data if r else []

    def _knowledge_search(self, db: Session, message: str, brand: str, model: str) -> list:
        r = self.knowledge.search(db, f"{brand} {model} 价格 配置", top_k=3, brand=brand, model=model)
        if r:
            items = r.data if isinstance(r.data, list) else []
            logger.info(f"Orchestrator: knowledge search returned {len(items)} items")
            return items
        return []

    def _handle_general(self, message: str, history: List[Dict], web_search: bool) -> str:
        search_text = ""
        if web_search:
            r = self.searcher.search_general(message)
            if r:
                items = r.data if isinstance(r.data, list) else []
                search_text = "\n".join(
                    f"[{i}] {it.get('title', '')}\n内容: {(it.get('content', '') or '')[:300]}"
                    for i, it in enumerate(items[:3], 1)
                )
        r = self.writer.generate_general_chat(message, history, search_text)
        return r.data.get("report", "") if r else "抱歉，暂时无法回复。"

    def _fallback_text(self, intent, results: list, car_info: dict) -> str:
        from app.agent.agent import Intent
        if intent == Intent.CAR_PRICE:
            b = car_info.get("brand", "")
            m = car_info.get("model", "")
            with_p = [r for r in results if r.get("price")]
            if with_p:
                from app.utils.helpers import format_price
                p = format_price(with_p[0].get("price"), "CNY")
                return f"**{b} {m} 参考价格**: {p}\n\n共找到 {len(results)} 条相关信息。"
            return f"已查到 {b} {m} 相关信息，但未提取到具体价格。"
        if intent == Intent.NEWS:
            parts = [f"- [{r.get('title','')}]({r.get('url','')})" for r in results[:5]]
            return "**最新汽车资讯**\n\n" + "\n".join(parts)
        if intent == Intent.CAR_COMPARE:
            return "已获取对比数据，正在生成详细对比报告..."
        return "已获取数据，正在生成分析报告..."
