"""
RAG 知识库管理 API — Semantic Structured Chunking + Hybrid Search
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional, List, Literal

from app.db.database import get_db
from app.db.models import RagDocument, RagChunk, RagChunkEmbedding
from sqlalchemy import func
from app.auth.dependencies import admin_required
from app.services.rag_service import rag_service, validate_car_json
from app.schemas.chunk import ChunkType, SearchFilters
from app.core.logging import logger

router = APIRouter(
    prefix="/admin/rag",
    tags=["知识库管理"],
    dependencies=[Depends(admin_required)],
)


# ═══════════════════════════════════════════════════════════════
#  Schemas
# ═══════════════════════════════════════════════════════════════

class CarIngestRequest(BaseModel):
    brand: str = Field(..., description="品牌")
    model: str = Field(..., description="车型")
    year: Optional[str] = Field(None, description="年份")
    price: Optional[str] = Field(None, description="官方售价")
    dealer_price: Optional[str] = Field(None, description="经销商报价")
    used_price: Optional[str] = Field(None, description="二手车价格")
    energy_type: Optional[str] = Field(None, description="能源类型")
    range_km: Optional[str] = Field(None, description="续航里程")
    horsepower: Optional[str] = Field(None, description="马力")
    battery: Optional[str] = Field(None, description="电池")
    transmission: Optional[str] = Field(None, description="变速箱")
    content: Optional[str] = Field(None, description="详细描述")
    source_url: Optional[str] = Field(None, description="来源URL")


class BatchIngestRequest(BaseModel):
    cars: List[CarIngestRequest] = Field(..., description="车辆列表")


class StructuredSearchRequest(BaseModel):
    """Typed structured search request with metadata filtering."""
    query: str = Field(..., description="搜索查询")
    top_k: int = Field(5, ge=1, le=50, description="返回结果数")
    brand: Optional[str] = Field(None, description="品牌过滤")
    model: Optional[str] = Field(None, description="车型过滤")
    chunk_type: Optional[str] = Field(None, description="Chunk类型: brand|model|feature|comparison")
    vehicle_type: Optional[str] = Field(None, description="车型类别: 轿车|SUV|MPV|跑车|皮卡")
    power_type: Optional[str] = Field(None, description="动力类型: 纯电动|增程式|插电混动|燃油|氢能")
    smart_drive: Optional[str] = Field(None, description="智驾等级: L2|L2+|L2++|L3|L4")
    price_range: Optional[str] = Field(None, description="价格区间")
    year: Optional[str] = Field(None, description="年份")
    topic: Optional[str] = Field(None, description="特性主题: 智驾|续航|动力|空间|安全|外观|座舱|价格")


class DocumentResponse(BaseModel):
    id: int
    title: str
    source_type: str
    source_uri: Optional[str]
    doc_status: str
    brand: Optional[str] = None
    model: Optional[str] = None
    year: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
#  Endpoints
# ═══════════════════════════════════════════════════════════════

@router.get("/stats")
def rag_stats(db: Session = Depends(get_db)):
    """获取知识库统计信息（含 Chunk 类型分布）"""
    return rag_service.get_stats(db)


@router.get("/documents")
def list_documents(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    brand: Optional[str] = Query(None, description="品牌过滤"),
    chunk_type: Optional[str] = Query(None, description="Chunk类型过滤"),
    db: Session = Depends(get_db),
):
    """列出知识库中的文档"""
    query = db.query(RagDocument).filter(RagDocument.is_deleted == False)

    if brand:
        query = query.filter(
            func.lower(RagDocument.metadata_['brand'].astext)== brand.lower()
        )

    total = query.count()
    docs = (
        query
        .order_by(RagDocument.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = []
    for d in docs:
        # Count chunks per type for this document
        chunk_counts = {}
        if chunk_type:
            chunks = (
                db.query(RagChunk)
                .filter(RagChunk.document_id == d.id,
                        RagChunk.is_deleted == False,
                        RagChunk.chunk_type == chunk_type)
                .all()
            )
        else:
            chunks = (
                db.query(RagChunk)
                .filter(RagChunk.document_id == d.id,
                        RagChunk.is_deleted == False)
                .all()
            )
        for c in chunks:
            chunk_counts[c.chunk_type] = chunk_counts.get(c.chunk_type, 0) + 1

        items.append({
            "id": d.id,
            "title": d.title,
            "source_type": d.source_type,
            "source_uri": d.source_uri,
            "doc_status": d.doc_status,
            "brand": d.metadata_.get("brand"),
            "model": d.metadata_.get("model"),
            "year": d.metadata_.get("year"),
            "energy_type": d.metadata_.get("energy_type"),
            "chunk_count": sum(chunk_counts.values()),
            "chunk_types": chunk_counts,
            "created_at": d.created_at.isoformat() if d.created_at else "",
        })

    return {"total": total, "items": items}


@router.post("/ingest")
def ingest_car(request: CarIngestRequest, db: Session = Depends(get_db)):
    """录入单条车辆数据到知识库（Semantic Structured Chunking）"""
    car_data = request.model_dump()
    ok, msg = validate_car_json(car_data)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    try:
        doc_id = rag_service.ingest_car_data(db, car_data)
        if doc_id:
            logger.info(f"Admin ingested car: {request.brand} {request.model} (doc_id={doc_id})")
            return {"status": "ok", "doc_id": doc_id, "message": f"已录入 {request.brand} {request.model}"}
        else:
            return {"status": "skipped", "doc_id": None, "message": "数据验证未通过"}
    except Exception as e:
        logger.exception("Ingest failed")
        raise HTTPException(status_code=500, detail="知识库录入失败，请稍后重试")


@router.post("/ingest/batch")
def ingest_batch(request: BatchIngestRequest, db: Session = Depends(get_db)):
    """批量录入车辆数据到知识库"""
    cars = [c.model_dump() for c in request.cars]
    valid_cars = []
    errors = []
    for car in cars:
        ok, msg = validate_car_json(car)
        if ok:
            valid_cars.append(car)
        else:
            errors.append(f"{car.get('brand', '?')} {car.get('model', '?')}: {msg}")

    count = rag_service.ingest_batch(db, valid_cars)
    return {
        "status": "ok",
        "ingested": count,
        "skipped": len(errors),
        "errors": errors[:10],
    }


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    """从知识库中删除文档"""
    success = rag_service.delete_document(db, doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"status": "ok", "message": f"文档 {doc_id} 已删除"}


@router.post("/reindex")
def reindex_sample_data(db: Session = Depends(get_db)):
    """录入内置的 5 辆示例车辆数据（用于快速测试）"""
    try:
        from test_rag import SAMPLE_CARS
    except ImportError:
        raise HTTPException(status_code=500, detail="测试数据模块不可用（生产环境已排除 test_*.py）")
    count = rag_service.ingest_batch(db, SAMPLE_CARS)
    return {
        "status": "ok",
        "ingested": count,
        "message": f"已录入 {count} 辆示例车辆到知识库",
    }


# ═══════════════════════════════════════════════════════════════
#  Structured Search
# ═══════════════════════════════════════════════════════════════

@router.post("/search")
def structured_search(request: StructuredSearchRequest, db: Session = Depends(get_db)):
    """结构化语义搜索 — 支持 Metadata Filtering + Hybrid Search (BM25 + Vector)

    支持的过滤维度:
      - brand: 品牌过滤 (如: 特斯拉, 比亚迪)
      - model: 车型过滤 (如: Model 3, 汉 EV)
      - chunk_type: brand|model|feature|comparison
      - vehicle_type: 轿车|SUV|MPV|跑车|皮卡
      - power_type: 纯电动|增程式|插电混动|燃油|氢能
      - smart_drive: L2|L2+|L2++|L3|L4
      - price_range: 价格区间
      - year: 年份
      - topic: 特性主题 (智驾|续航|动力|空间|安全|外观|座舱|价格)

    Hybrid Search: BM25 关键词预过滤 + Vector 语义相似度 + 分数融合
    """
    filters = SearchFilters(
        brand=request.brand,
        model=request.model,
        chunk_type=ChunkType(request.chunk_type) if request.chunk_type else None,
        vehicle_type=request.vehicle_type,
        power_type=request.power_type,
        smart_drive=request.smart_drive,
        price_range=request.price_range,
        year=request.year,
        topic=request.topic,
    )

    results = rag_service.structured_search(db, request.query, filters, top_k=request.top_k)

    return {
        "status": "ok",
        "query": request.query,
        "filters": request.model_dump(exclude_none=True, exclude={"query", "top_k"}),
        "count": len(results),
        "results": [
            {
                "chunk_id": r.chunk_id,
                "chunk_type": r.chunk_type,
                "brand": r.brand,
                "model": r.model,
                "content": r.content[:300] + ("..." if len(r.content) > 300 else ""),
                "full_content": r.content,
                "similarity": r.similarity,
                "bm25_score": r.bm25_score,
                "combined_score": r.combined_score,
                "metadata": r.metadata.model_dump(),
                "retrieval_keywords": r.retrieval_keywords,
                "document_id": r.document_id,
                "title": r.title,
                "source_url": r.source_url,
            }
            for r in results
        ],
    }


@router.get("/search/simple")
def simple_search(
    q: str = Query(..., description="搜索关键词"),
    top_k: int = Query(5, ge=1, le=50),
    brand: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    chunk_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """简化的 GET 搜索接口"""
    filters = {}
    if brand:
        filters["brand"] = brand
    if model:
        filters["model"] = model
    if chunk_type:
        filters["chunk_type"] = chunk_type

    results = rag_service.search(db, q, top_k=top_k, filters=filters or None, hybrid=True)

    return {
        "status": "ok",
        "query": q,
        "count": len(results),
        "results": [
            {
                "chunk_id": r["chunk_id"],
                "chunk_type": r["chunk_type"],
                "brand": r["brand"],
                "model": r["model"],
                "content": r["content"][:300] + ("..." if len(r["content"]) > 300 else ""),
                "similarity": r["similarity"],
                "bm25_score": r.get("bm25_score", 0),
                "combined_score": r.get("combined_score", 0),
                "title": r["title"],
                "topic": r.get("topic", ""),
            }
            for r in results
        ],
    }


# ═══════════════════════════════════════════════════════════════
#  导入导出
# ═══════════════════════════════════════════════════════════════

@router.post("/import/file")
async def import_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin=Depends(admin_required),
):
    """上传文件导入知识库（支持 .pdf / .md / .txt / .json / .csv）。"""
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    is_binary = ext in ("pdf",)

    raw = await file.read()
    content = raw if is_binary else raw.decode("utf-8-sig")

    from app.multi_agent.knowledge import KnowledgeAgent
    agent = KnowledgeAgent()
    result = agent.import_from_file(db, file.filename or "unknown", content, is_binary=is_binary)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return {"status": "ok", "filename": file.filename, **result.data}


@router.get("/export")
def export_knowledge_base(
    fmt: Literal["json", "md", "markdown"] = Query("json"),
    brand: str = Query(""),
    doc_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _admin=Depends(admin_required),
):
    """导出知识库为 JSON 或 Markdown。"""
    from app.multi_agent.knowledge import KnowledgeAgent
    agent = KnowledgeAgent()
    if fmt in ("md", "markdown"):
        result = agent.export_markdown(db, doc_id)
    else:
        result = agent.export_json(db, brand or None)
    if not result.success:
        raise HTTPException(status_code=500, detail="导出失败")
    return {"status": "ok", "data": result.data}


@router.get("/documents/{doc_id}/chunks")
def get_document_chunks(
    doc_id: int,
    chunk_type: Optional[str] = Query(None, description="Chunk类型过滤"),
    db: Session = Depends(get_db),
    _admin=Depends(admin_required),
):
    """获取文档的 Chunk 详情（含 chunk_id, chunk_type, metadata）。"""
    doc = db.query(RagDocument).filter(
        RagDocument.id == doc_id, RagDocument.is_deleted == False
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    q = db.query(RagChunk).filter(
        RagChunk.document_id == doc_id, RagChunk.is_deleted == False
    )
    if chunk_type:
        q = q.filter(RagChunk.chunk_type == chunk_type)
    chunks = q.order_by(RagChunk.chunk_index).all()

    return {
        "id": doc.id,
        "title": doc.title,
        "source_type": doc.source_type,
        "source_uri": doc.source_uri,
        "metadata": doc.metadata_,
        "created_at": doc.created_at.isoformat() if doc.created_at else "",
        "chunks": [
            {
                "chunk_id": c.chunk_id,
                "index": c.chunk_index,
                "chunk_type": c.chunk_type,
                "content": c.content,
                "token_count": c.token_count,
                "metadata": c.metadata_,
            }
            for c in chunks
        ],
    }


@router.get("/documents/{doc_id}/content")
def get_document_content(
    doc_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(admin_required),
):
    """获取文档详细内容（含 chunks）— 向后兼容。"""
    doc = db.query(RagDocument).filter(RagDocument.id == doc_id, RagDocument.is_deleted == False).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    chunks = (
        db.query(RagChunk)
        .filter(RagChunk.document_id == doc_id, RagChunk.is_deleted == False)
        .order_by(RagChunk.chunk_index)
        .all()
    )
    return {
        "id": doc.id,
        "title": doc.title,
        "source_type": doc.source_type,
        "source_uri": doc.source_uri,
        "metadata": doc.metadata_,
        "created_at": doc.created_at.isoformat() if doc.created_at else "",
        "chunks": [
            {
                "chunk_id": c.chunk_id,
                "index": c.chunk_index,
                "chunk_type": c.chunk_type,
                "content": c.content,
                "token_count": c.token_count,
            }
            for c in chunks
        ],
    }
