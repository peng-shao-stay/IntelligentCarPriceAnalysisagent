"""
Search MCP Server — wraps Serper.dev Google Search as an MCP-compatible tool server.

Exposes tools:
  - search_car_price  —  multi-dimension car price search
  - search_news       —  automotive news search
  - search_general    —  general web search
  - search_comparison —  car comparison search

Run independently:
  python -m mcp_servers.search_server --port 9100
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Any, Dict, List

# Ensure project root is on path when running standalone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_servers.base import BaseMCPServer, MCPToolDef
from app.services.web_search_service import web_search as _web_search_svc


def _extract_price(text: str) -> float | None:
    for pattern in [
        r"￥([0-9,]+\.?[0-9]*)",
        r"([0-9]+\.?[0-9]*)万元",
        r"([0-9]+\.?[0-9]*)万",
        r"([0-9,]+\.?[0-9]*)元",
    ]:
        m = re.search(pattern, text)
        if not m:
            continue
        price = float(m.group(1).replace(",", ""))
        if "万" in pattern:
            price *= 10000
        return price
    return None


def _detect_trend(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["降价", "优惠", "下调", "降低"]):
        return "down"
    if any(w in t for w in ["涨价", "上调", "上涨", "提升"]):
        return "up"
    return "stable"


class SearchMCPServer:
    """Factory for the Search MCP Server application."""

    def __init__(self, port: int = 9100, api_key: str = None):
        self.server = BaseMCPServer(
            name="search",
            port=port,
            api_key=api_key,
            description="Automotive web search MCP server — car prices, news, comparisons",
        )
        self._register_tools()
        self.app = self.server.app

    def _register_tools(self) -> None:
        self.server.register_tools([
            MCPToolDef(
                name="search_car_price",
                description="多维度搜索汽车价格：官方售价、经销商报价、二手车价格、配置参数、市场行情、用户评价",
                handler=self._handle_search_car_price,
                input_schema={
                    "type": "object",
                    "properties": {
                        "brand": {"type": "string", "description": "汽车品牌，如 特斯拉"},
                        "model": {"type": "string", "description": "车型，如 Model 3"},
                        "version": {"type": "string", "description": "版本/年款，如 2024款"},
                    },
                    "required": ["brand", "model"],
                },
            ),
            MCPToolDef(
                name="search_news",
                description="搜索最新汽车行业新闻、资讯和动态",
                handler=self._handle_search_news,
                input_schema={
                    "type": "object",
                    "properties": {
                        "keyword": {"type": "string", "description": "搜索关键词"},
                        "limit": {"type": "integer", "description": "返回上限", "default": 5},
                    },
                    "required": ["keyword"],
                },
            ),
            MCPToolDef(
                name="search_general",
                description="通用网页搜索，用于非汽车专属的泛化查询",
                handler=self._handle_search_general,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索查询"},
                        "max_results": {"type": "integer", "description": "最大结果数", "default": 5},
                    },
                    "required": ["query"],
                },
            ),
            MCPToolDef(
                name="search_comparison",
                description="对比搜索两款车型的数据",
                handler=self._handle_search_comparison,
                input_schema={
                    "type": "object",
                    "properties": {
                        "car1_brand": {"type": "string", "description": "第一款车品牌"},
                        "car1_model": {"type": "string", "description": "第一款车型号"},
                        "car2_brand": {"type": "string", "description": "第二款车品牌"},
                        "car2_model": {"type": "string", "description": "第二款车型号"},
                    },
                    "required": ["car1_brand", "car1_model", "car2_brand", "car2_model"],
                },
            ),
        ])

    # ── Handlers ───────────────────────────────────────────

    def _handle_search_car_price(self, params: Dict[str, Any]) -> List[Dict]:
        brand = params["brand"]
        model = params["model"]
        version = params.get("version")

        results = _web_search_svc.search_car(brand=brand, model=model, version=version, top_k=10)
        results = _web_search_svc.filter_quality(results)

        output = []
        for r in results:
            text = r.title + " " + r.content
            output.append({
                "brand": brand,
                "model": model,
                "version": version or "",
                "price": _extract_price(text),
                "currency": "CNY",
                "trend": _detect_trend(text),
                "title": r.title,
                "url": r.url,
                "content": r.content[:500],
                "source": r.source,
                "credibility_score": r.credibility_score,
                "credibility_tier": r.credibility_tier,
                "dimension": r.dimension,
                "published_date": r.published_date,
            })

        self.server.log.info(
            f"search_car_price done | {brand} {model} | "
            f"results={len(output)} | "
            f"with_price={sum(1 for o in output if o['price'])}"
        )
        return output

    def _handle_search_news(self, params: Dict[str, Any]) -> List[Dict]:
        keyword = params["keyword"]
        limit = params.get("limit", 5)

        results = _web_search_svc.search_news(keyword=keyword, top_k=limit)
        results = _web_search_svc.filter_quality(results)

        output = []
        for r in results:
            output.append({
                "title": r.title,
                "url": r.url,
                "content": r.content[:500],
                "source": r.source,
                "credibility_score": r.credibility_score,
                "credibility_tier": r.credibility_tier,
                "published_date": r.published_date,
            })

        self.server.log.info(f"search_news done | keyword={keyword} | results={len(output)}")
        return output

    def _handle_search_general(self, params: Dict[str, Any]) -> List[Dict]:
        query = params["query"]
        max_results = params.get("max_results", 5)

        from app.services.web_search_service import web_search
        results = web_search.search_general(query, max_results=max_results)

        self.server.log.info(f"search_general done | query={query[:60]} | results={len(results)}")
        return results

    def _handle_search_comparison(self, params: Dict[str, Any]) -> Dict[str, Any]:
        car1 = f"{params['car1_brand']} {params['car1_model']}"
        car2 = f"{params['car2_brand']} {params['car2_model']}"

        result = _web_search_svc.search_comparison(car1, car2)
        self.server.log.info(f"search_comparison done | {car1} vs {car2}")
        return result

    def run(self) -> None:
        self.server.run()


# ── Standalone entry point ───────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Search MCP Server")
    parser.add_argument("--port", type=int, default=9100, help="Server port (default: 9100)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Bind host")
    parser.add_argument("--api-key", type=str, default=os.getenv("MCP_SEARCH_API_KEY"), help="API key for auth")
    args = parser.parse_args()

    server = SearchMCPServer(port=args.port, api_key=args.api_key)
    server.server.host = args.host
    server.run()


if __name__ == "__main__":
    main()
