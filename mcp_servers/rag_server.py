"""
RAG Vector MCP Server — semantic search over the car knowledge base.

Exposes tools:
  - vector_search       —  pgvector cosine similarity search
  - embed_query         —  generate embedding for a query
  - build_rag_context   —  build LLM-ready context from search results
  - get_rag_stats       —  knowledge base statistics
  - ingest_car_data     —  ingest a car data record
  - ingest_free_text    —  ingest arbitrary text

Run independently:
  python -m mcp_servers.rag_server --port 9102
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_servers.base import BaseMCPServer, MCPToolDef


class RAGVectorMCPServer:
    """MCP server for RAG / vector search operations."""

    def __init__(self, port: int = 9102, api_key: str = None):
        self.server = BaseMCPServer(
            name="rag-vector",
            port=port,
            api_key=api_key,
            description="RAG Vector MCP server — semantic search, embeddings, knowledge base management",
        )
        self._register_tools()
        self.app = self.server.app

    def _get_db(self):
        from app.db.database import SessionLocal
        return SessionLocal()

    def _get_rag(self):
        from app.services.rag_service import rag_service
        return rag_service

    def _register_tools(self) -> None:
        self.server.register_tools([
            MCPToolDef(
                name="vector_search",
                description="向量语义搜索：基于 pgvector 余弦相似度的知识库检索",
                handler=self._handle_vector_search,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索查询"},
                        "top_k": {"type": "integer", "description": "返回结果数", "default": 5},
                        "brand": {"type": "string", "description": "按品牌过滤（可选）"},
                        "model": {"type": "string", "description": "按车型过滤（可选）"},
                    },
                    "required": ["query"],
                },
            ),
            MCPToolDef(
                name="build_rag_context",
                description="构建 LLM 可用的知识库上下文文本",
                handler=self._handle_build_context,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "查询文本"},
                        "top_k": {"type": "integer", "description": "检索文档数", "default": 5},
                    },
                    "required": ["query"],
                },
            ),
            MCPToolDef(
                name="get_rag_stats",
                description="获取知识库统计信息：文档数、分块数、品牌列表等",
                handler=self._handle_get_stats,
                input_schema={
                    "type": "object",
                    "properties": {},
                },
            ),
            MCPToolDef(
                name="ingest_car_data",
                description="录入结构化汽车数据到知识库",
                handler=self._handle_ingest_car,
                input_schema={
                    "type": "object",
                    "properties": {
                        "brand": {"type": "string", "description": "品牌"},
                        "model": {"type": "string", "description": "车型"},
                        "year": {"type": "string", "description": "年份"},
                        "price": {"type": "number", "description": "价格"},
                        "dealer_price": {"type": "number", "description": "经销商报价"},
                        "energy_type": {"type": "string", "description": "能源类型"},
                        "range_km": {"type": "number", "description": "续航里程"},
                        "content": {"type": "string", "description": "详细描述"},
                        "source_url": {"type": "string", "description": "来源URL"},
                    },
                    "required": ["brand", "model"],
                },
                permissions=["kb:write"],
            ),
            MCPToolDef(
                name="ingest_free_text",
                description="录入自由文本到知识库",
                handler=self._handle_ingest_text,
                input_schema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "文本内容"},
                        "title": {"type": "string", "description": "标题（可选）"},
                        "brand": {"type": "string", "description": "关联品牌（可选）"},
                        "model": {"type": "string", "description": "关联车型（可选）"},
                    },
                    "required": ["content"],
                },
                permissions=["kb:write"],
            ),
        ])

    # ── Handlers ───────────────────────────────────────────

    def _handle_vector_search(self, params: Dict[str, Any]) -> List[Dict]:
        query = params["query"]
        top_k = params.get("top_k", 5)
        filters = {}
        if params.get("brand"):
            filters["brand"] = params["brand"]
        if params.get("model"):
            filters["model"] = params["model"]

        rag = self._get_rag()
        db = self._get_db()
        try:
            results = rag.search(db, query, top_k=top_k, filters=filters or None)
            self.server.log.info(
                f"vector_search done | query={query[:60]} | results={len(results)}"
            )
            return results
        finally:
            db.close()

    def _handle_build_context(self, params: Dict[str, Any]) -> Dict[str, str]:
        query = params["query"]
        top_k = params.get("top_k", 5)

        rag = self._get_rag()
        db = self._get_db()
        try:
            context = rag.build_context(db, query, top_k=top_k)
            self.server.log.info(
                f"build_context done | query={query[:60]} | len={len(context)}"
            )
            return {"context": context, "query": query}
        finally:
            db.close()

    def _handle_get_stats(self, params: Dict[str, Any]) -> Dict[str, Any]:
        rag = self._get_rag()
        db = self._get_db()
        try:
            stats = rag.get_stats(db)
            self.server.log.info(f"get_stats done | docs={stats['document_count']}")
            return stats
        finally:
            db.close()

    def _handle_ingest_car(self, params: Dict[str, Any]) -> Dict[str, Any]:
        rag = self._get_rag()
        db = self._get_db()
        try:
            doc_id = rag.ingest_car_data(db, params)
            db.commit()
            self.server.log.info(f"ingest_car_data done | doc_id={doc_id}")
            return {"success": doc_id is not None, "document_id": doc_id}
        except Exception as exc:
            db.rollback()
            self.server.log.error(f"ingest_car_data failed | error={exc}")
            return {"success": False, "error": str(exc)}
        finally:
            db.close()

    def _handle_ingest_text(self, params: Dict[str, Any]) -> Dict[str, Any]:
        content = params["content"]
        title = params.get("title")
        brand = params.get("brand")
        model = params.get("model")

        rag = self._get_rag()
        db = self._get_db()
        try:
            doc_id = rag.ingest_free_text(
                db, content=content, title=title, brand=brand, model=model,
            )
            db.commit()
            self.server.log.info(f"ingest_free_text done | doc_id={doc_id}")
            return {"success": doc_id is not None, "document_id": doc_id, "title": title}
        except Exception as exc:
            db.rollback()
            self.server.log.error(f"ingest_free_text failed | error={exc}")
            return {"success": False, "error": str(exc)}
        finally:
            db.close()

    def run(self) -> None:
        self.server.run()


# ── Standalone entry point ───────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RAG Vector MCP Server")
    parser.add_argument("--port", type=int, default=9102, help="Server port (default: 9102)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Bind host")
    parser.add_argument("--api-key", type=str, default=os.getenv("MCP_RAG_API_KEY"), help="API key")
    args = parser.parse_args()

    server = RAGVectorMCPServer(port=args.port, api_key=args.api_key)
    server.server.host = args.host
    server.run()


if __name__ == "__main__":
    main()
