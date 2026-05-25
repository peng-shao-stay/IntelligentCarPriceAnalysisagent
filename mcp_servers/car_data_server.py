"""
Car Data MCP Server — structured car database operations.

Exposes tools:
  - query_car_price   —  query car_price_snapshots table
  - list_brands       —  list all known brands
  - list_models       —  list models for a brand
  - query_news        —  query news_articles table
  - get_car_stats     —  aggregate statistics

Run independently:
  python -m mcp_servers.car_data_server --port 9101
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_servers.base import BaseMCPServer, MCPToolDef


class CarDataMCPServer:
    """MCP server for structured car database queries."""

    def __init__(self, port: int = 9101, api_key: str = None):
        self.server = BaseMCPServer(
            name="car-data",
            port=port,
            api_key=api_key,
            description="Car database MCP server — price snapshots, brands, models, news",
        )
        self._register_tools()
        self.app = self.server.app

    def _get_db(self):
        """Create a database session."""
        from app.db.database import SessionLocal
        return SessionLocal()

    def _register_tools(self) -> None:
        self.server.register_tools([
            MCPToolDef(
                name="query_car_price",
                description="查询汽车价格快照数据（结构化数据库）",
                handler=self._handle_query_car_price,
                input_schema={
                    "type": "object",
                    "properties": {
                        "brand": {"type": "string", "description": "品牌名称"},
                        "model": {"type": "string", "description": "车型名称"},
                        "version": {"type": "string", "description": "版本（可选）"},
                        "limit": {"type": "integer", "description": "返回上限", "default": 10},
                    },
                    "required": ["brand", "model"],
                },
            ),
            MCPToolDef(
                name="list_brands",
                description="列出数据库中所有已知汽车品牌",
                handler=self._handle_list_brands,
                input_schema={
                    "type": "object",
                    "properties": {},
                },
            ),
            MCPToolDef(
                name="list_models",
                description="列出指定品牌下的所有车型",
                handler=self._handle_list_models,
                input_schema={
                    "type": "object",
                    "properties": {
                        "brand": {"type": "string", "description": "品牌名称"},
                    },
                    "required": ["brand"],
                },
            ),
            MCPToolDef(
                name="query_news",
                description="查询已存储的汽车新闻文章",
                handler=self._handle_query_news,
                input_schema={
                    "type": "object",
                    "properties": {
                        "keyword": {"type": "string", "description": "搜索关键词"},
                        "brand": {"type": "string", "description": "关联品牌（可选）"},
                        "limit": {"type": "integer", "description": "返回上限", "default": 10},
                    },
                    "required": ["keyword"],
                },
            ),
            MCPToolDef(
                name="get_car_stats",
                description="获取汽车价格统计信息：最低价、最高价、均价、数据量",
                handler=self._handle_get_car_stats,
                input_schema={
                    "type": "object",
                    "properties": {
                        "brand": {"type": "string", "description": "品牌（可选，不填则全局统计）"},
                    },
                },
            ),
        ])

    # ── Handlers ───────────────────────────────────────────

    def _handle_query_car_price(self, params: Dict[str, Any]) -> List[Dict]:
        from app.db.models import CarPriceSnapshot

        brand = params["brand"]
        model = params["model"]
        version = params.get("version")
        limit = params.get("limit", 10)

        db = self._get_db()
        try:
            q = (
                db.query(CarPriceSnapshot)
                .filter(
                    CarPriceSnapshot.is_deleted == False,
                    CarPriceSnapshot.brand_name.ilike(f"%{brand}%"),
                    CarPriceSnapshot.model_name.ilike(f"%{model}%"),
                )
            )
            if version:
                q = q.filter(CarPriceSnapshot.version_name.ilike(f"%{version}%"))
            rows = q.order_by(CarPriceSnapshot.created_at.desc()).limit(limit).all()

            results = []
            for r in rows:
                results.append({
                    "brand": r.brand_name,
                    "model": r.model_name,
                    "version": r.version_name or "",
                    "price": float(r.price) if r.price else None,
                    "currency": r.currency,
                    "source": r.source or "数据库",
                    "trend": r.trend or "stable",
                    "region": r.region or "",
                    "url": r.source_url or "",
                    "recorded_at": r.created_at.isoformat() if r.created_at else "",
                })

            self.server.log.info(
                f"query_car_price done | {brand} {model} | results={len(results)}"
            )
            return results
        finally:
            db.close()

    def _handle_list_brands(self, params: Dict[str, Any]) -> List[Dict]:
        from app.db.models import CarPriceSnapshot
        from sqlalchemy import func

        db = self._get_db()
        try:
            rows = (
                db.query(
                    CarPriceSnapshot.brand_name,
                    func.count(CarPriceSnapshot.id).label("count"),
                )
                .filter(CarPriceSnapshot.is_deleted == False)
                .group_by(CarPriceSnapshot.brand_name)
                .order_by(func.count(CarPriceSnapshot.id).desc())
                .all()
            )
            results = [{"brand": r[0], "record_count": r[1]} for r in rows]
            self.server.log.info(f"list_brands done | brands={len(results)}")
            return results
        finally:
            db.close()

    def _handle_list_models(self, params: Dict[str, Any]) -> List[Dict]:
        from app.db.models import CarPriceSnapshot
        from sqlalchemy import func

        brand = params["brand"]
        db = self._get_db()
        try:
            rows = (
                db.query(
                    CarPriceSnapshot.model_name,
                    func.min(CarPriceSnapshot.price).label("min_price"),
                    func.max(CarPriceSnapshot.price).label("max_price"),
                    func.count(CarPriceSnapshot.id).label("count"),
                )
                .filter(
                    CarPriceSnapshot.is_deleted == False,
                    CarPriceSnapshot.brand_name.ilike(f"%{brand}%"),
                )
                .group_by(CarPriceSnapshot.model_name)
                .order_by(CarPriceSnapshot.model_name)
                .all()
            )
            results = [
                {
                    "model": r[0],
                    "min_price": float(r[1]) if r[1] else None,
                    "max_price": float(r[2]) if r[2] else None,
                    "record_count": r[3],
                }
                for r in rows
            ]
            self.server.log.info(f"list_models done | {brand} | models={len(results)}")
            return results
        finally:
            db.close()

    def _handle_query_news(self, params: Dict[str, Any]) -> List[Dict]:
        from app.db.models import NewsArticle

        keyword = params["keyword"]
        brand = params.get("brand")
        limit = params.get("limit", 10)

        db = self._get_db()
        try:
            q = (
                db.query(NewsArticle)
                .filter(
                    NewsArticle.is_deleted == False,
                    (NewsArticle.title.ilike(f"%{keyword}%"))
                    | (NewsArticle.content.ilike(f"%{keyword}%")),
                )
            )
            if brand:
                q = q.filter(NewsArticle.related_brand.ilike(f"%{brand}%"))
            rows = q.order_by(NewsArticle.published_at.desc()).limit(limit).all()

            results = []
            for r in rows:
                results.append({
                    "title": r.title,
                    "url": r.url or "",
                    "content": (r.content or r.summary or "")[:500],
                    "source": r.source or "",
                    "brand": r.related_brand or "",
                    "published_at": r.published_at.isoformat() if r.published_at else "",
                })

            self.server.log.info(f"query_news done | keyword={keyword} | results={len(results)}")
            return results
        finally:
            db.close()

    def _handle_get_car_stats(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from app.db.models import CarPriceSnapshot
        from sqlalchemy import func

        brand = params.get("brand")
        db = self._get_db()
        try:
            q = db.query(CarPriceSnapshot).filter(CarPriceSnapshot.is_deleted == False)
            if brand:
                q = q.filter(CarPriceSnapshot.brand_name.ilike(f"%{brand}%"))

            stats = q.with_entities(
                func.count(CarPriceSnapshot.id).label("total"),
                func.min(CarPriceSnapshot.price).label("min_price"),
                func.max(CarPriceSnapshot.price).label("max_price"),
                func.avg(CarPriceSnapshot.price).label("avg_price"),
            ).first()

            result = {
                "total_records": stats[0] if stats else 0,
                "min_price": float(stats[1]) if stats[1] else None,
                "max_price": float(stats[2]) if stats[2] else None,
                "avg_price": round(float(stats[3]), 2) if stats[3] else None,
                "brand_filter": brand or "全部",
            }
            self.server.log.info(f"get_car_stats done | {result}")
            return result
        finally:
            db.close()

    def run(self) -> None:
        self.server.run()


# ── Standalone entry point ───────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Car Data MCP Server")
    parser.add_argument("--port", type=int, default=9101, help="Server port (default: 9101)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Bind host")
    parser.add_argument("--api-key", type=str, default=os.getenv("MCP_CAR_DATA_API_KEY"), help="API key")
    args = parser.parse_args()

    server = CarDataMCPServer(port=args.port, api_key=args.api_key)
    server.server.host = args.host
    server.run()


if __name__ == "__main__":
    main()
