"""
Knowledge Agent — 知识库管理 + RAG 检索 + 文档导入导出
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.multi_agent.base import AgentResult, BaseAgent
from app.core.logging import logger
from app.db.models import RagDocument
from app.services.rag_service import rag_service


class KnowledgeAgent(BaseAgent):
    """知识库 Agent：RAG 查询、文档管理、导入导出。"""

    name = "knowledge"

    # ── 检索 ──────────────────────────────────────────────────

    def search(self, db: Session, query: str, top_k: int = 5,
               brand: str = None, model: str = None) -> AgentResult:
        filters = {}
        if brand:
            filters["brand"] = brand
        if model:
            filters["model"] = model
        results = rag_service.search(db, query, top_k=top_k, filters=filters or None)
        if not results:
            return AgentResult.fail(f"知识库中未查到 '{query}' 相关信息")
        return AgentResult.ok(results)

    def build_context(self, db: Session, query: str, top_k: int = 5) -> AgentResult:
        context = rag_service.build_context(db, query, top_k=top_k)
        if not context:
            return AgentResult.fail("知识库上下文为空")
        return AgentResult.ok(context)

    # ── 导入 ──────────────────────────────────────────────────

    def import_json(self, db: Session, json_str: str) -> AgentResult:
        """导入 JSON 格式车辆数据到知识库。"""
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return AgentResult.fail(f"JSON 格式错误: {e}")
        cars = data if isinstance(data, list) else [data]
        count = rag_service.ingest_batch(db, cars)
        return AgentResult.ok({"ingested": count, "total": len(cars)})

    def import_csv(self, db: Session, csv_content: str) -> AgentResult:
        """导入 CSV 格式车辆数据。"""
        reader = csv.DictReader(io.StringIO(csv_content))
        cars = []
        for row in reader:
            car = {k.strip(): v.strip() for k, v in row.items() if v and v.strip()}
            if car.get("brand") and car.get("model"):
                cars.append(car)
        if not cars:
            return AgentResult.fail("CSV 中未找到有效车辆数据（需要 brand, model 列）")
        count = rag_service.ingest_batch(db, cars)
        return AgentResult.ok({"ingested": count, "total": len(cars)})

    def import_text(self, db: Session, content: str, title: str = None,
                    brand: str = None, model: str = None) -> AgentResult:
        """导入自由文本到知识库。"""
        doc_id = rag_service.ingest_free_text(
            db=db, content=content, title=title, brand=brand, model=model
        )
        if doc_id is None:
            return AgentResult.fail("导入失败或内容重复")
        return AgentResult.ok({"document_id": doc_id})

    def import_from_file(self, db: Session, filename: str, content,
                         is_binary: bool = False) -> AgentResult:
        """根据文件扩展名自动选择导入方式。

        支持 .pdf（二进制）、.md、.txt、.json、.csv。
        is_binary=True 时 content 按 bytes 处理。
        """
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        title = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]

        if ext == "pdf":
            if not is_binary or not isinstance(content, bytes):
                return AgentResult.fail("PDF 文件需要以二进制模式上传")
            text = self._parse_pdf(content)
            return self._ingest_parsed_text(db, text, title=title, source_type="pdf")

        # Text-based formats
        if isinstance(content, bytes):
            content = content.decode("utf-8-sig")

        if ext == "md":
            text = self._parse_markdown(content)
            return self._ingest_parsed_text(db, text, title=title, source_type="markdown")
        elif ext == "txt":
            text = self._parse_text(content)
            return self._ingest_parsed_text(db, text, title=title, source_type="text")
        elif ext == "json":
            return self.import_json(db, content)
        elif ext == "csv":
            return self.import_csv(db, content)
        else:
            return AgentResult.fail(f"不支持的文件格式: .{ext}。支持的格式: pdf, md, txt, json, csv")

    # ── File Parsers ───────────────────────────────────────────

    def _parse_pdf(self, content: bytes) -> str:
        """Extract text from PDF binary content using pypdf."""
        from io import BytesIO
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(content))
        texts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                texts.append(page_text)
        text = "\n\n".join(texts)
        if not text.strip():
            return ""
        logger.info(f"Parsed PDF: {len(text)} chars from {len(texts)} pages")
        return text

    def _parse_markdown(self, content: str) -> str:
        """Convert Markdown to structured plain text using python-markdown."""
        import markdown
        from bs4 import BeautifulSoup

        html = markdown.markdown(content)
        soup = BeautifulSoup(html, "lxml")
        # Preserve heading hierarchy for semantic chunk boundaries
        text = soup.get_text(separator="\n", strip=True)
        return text

    def _parse_text(self, content: str) -> str:
        """Clean and normalize plain text — collapse whitespace but keep paragraphs."""
        content = re.sub(r'[ \t]+', ' ', content)
        content = re.sub(r'\n{3,}', '\n\n', content)
        return content.strip()

    def _ingest_parsed_text(self, db: Session, text: str, title: str,
                            source_type: str) -> AgentResult:
        """Ingest parsed document text, auto-detecting brand/model from content."""
        if not text or not text.strip():
            return AgentResult.fail("文档内容为空，无法导入")

        from app.utils.chunking import identify_brand, identify_model
        brand = identify_brand(text)
        model = identify_model(text, brand=brand)
        car_info = {"brand": brand, "model": model}

        doc_id = rag_service.ingest_free_text(
            db=db, content=text, title=title,
            brand=car_info.get("brand"),
            model=car_info.get("model"),
            source_type=source_type,
        )
        if doc_id is None:
            return AgentResult.fail("导入失败或内容重复")
        return AgentResult.ok({
            "document_id": doc_id,
            "title": title,
            "brand_detected": car_info.get("brand"),
            "model_detected": car_info.get("model"),
        })

    # ── 导出 ──────────────────────────────────────────────────

    def export_json(self, db: Session, brand: str = None) -> AgentResult:
        """导出知识库为 JSON。"""
        query = db.query(RagDocument).filter(RagDocument.is_deleted == False)
        if brand:
            query = query.filter(
                func.lower(func.jsonb_extract_path_text(RagDocument.metadata_, 'brand'))
                == brand.lower()
            )
        docs = query.order_by(RagDocument.created_at.desc()).limit(500).all()
        data = []
        for doc in docs:
            data.append({
                "id": doc.id,
                "title": doc.title,
                "source_type": doc.source_type,
                "brand": doc.metadata_.get("brand", ""),
                "model": doc.metadata_.get("model", ""),
                "year": doc.metadata_.get("year", ""),
                "created_at": doc.created_at.isoformat() if doc.created_at else "",
            })
        return AgentResult.ok(data)

    def export_markdown(self, db: Session, doc_id: int = None) -> AgentResult:
        """导出知识库文档为 Markdown 报告。"""
        from app.db.models import RagChunk

        if doc_id:
            docs = db.query(RagDocument).filter(
                RagDocument.id == doc_id, RagDocument.is_deleted == False
            ).all()
        else:
            docs = db.query(RagDocument).filter(
                RagDocument.is_deleted == False
            ).order_by(RagDocument.created_at.desc()).limit(50).all()

        lines = ["# 汽车知识库报告\n"]
        for doc in docs:
            lines.append(f"## {doc.title}")
            lines.append(f"- **类型**: {doc.source_type}")
            lines.append(f"- **创建时间**: {doc.created_at.isoformat() if doc.created_at else '未知'}")
            meta = doc.metadata_
            if meta.get("brand"):
                lines.append(f"- **品牌**: {meta['brand']}")
            if meta.get("model"):
                lines.append(f"- **车型**: {meta['model']}")
            if meta.get("year"):
                lines.append(f"- **年份**: {meta['year']}")
            # Get first chunk content
            chunk = db.query(RagChunk).filter(
                RagChunk.document_id == doc.id,
                RagChunk.is_deleted == False,
            ).order_by(RagChunk.chunk_index).first()
            if chunk:
                lines.append(f"\n{chunk.content[:200]}...\n")
            lines.append("---\n")

        return AgentResult.ok("\n".join(lines))

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self, db: Session) -> AgentResult:
        return AgentResult.ok(rag_service.get_stats(db))
