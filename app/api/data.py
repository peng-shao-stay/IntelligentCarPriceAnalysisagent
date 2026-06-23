"""
数据管理 API — 基于 RAG 知识库的区块（chunks）管理
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.db.models import RagDocument, RagChunk
from app.api.auth import get_current_admin_user, get_current_user
from app.core.logging import logger

router = APIRouter(prefix="/data", tags=["数据管理"])


@router.get("/list")
def list_chunks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    brand: str = Query(""),
    keyword: str = Query(""),
    chunk_type: str = Query(""),
    sort_field: str = Query("created_at"),
    sort_order: str = Query("desc"),
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """列出 RAG 知识库区块（RagChunk）。"""
    query = db.query(RagChunk).filter(RagChunk.is_deleted == False)

    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            (RagChunk.content.ilike(like))
            | (RagChunk.chunk_id.ilike(like))
            | (RagChunk.metadata_['brand'].astext.ilike(like))
            | (RagChunk.metadata_['model'].astext.ilike(like))
        )
    if brand:
        from sqlalchemy import func
        query = query.filter(
            func.lower(RagChunk.metadata_['brand'].astext) == brand.lower()
        )
    if chunk_type:
        query = query.filter(RagChunk.chunk_type == chunk_type)

    # Sorting — allow safe fields only
    allowed_sort = {"created_at", "updated_at", "id", "chunk_type", "chunk_index"}
    sort_col_name = sort_field if sort_field in allowed_sort else "created_at"
    sort_col = getattr(RagChunk, sort_col_name)
    if sort_order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    total = query.count()
    chunks = query.offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for c in chunks:
        meta = c.metadata_ or {}
        items.append({
            "id": c.id,
            "document_id": c.document_id,
            "chunk_id": c.chunk_id,
            "chunk_type": c.chunk_type,
            "chunk_index": c.chunk_index,
            "brand_name": meta.get("brand", ""),
            "model_name": meta.get("model", ""),
            "price_range": meta.get("price_range", ""),
            "year": meta.get("year", ""),
            "vehicle_type": meta.get("vehicle_type", ""),
            "power_type": meta.get("power_type", []),
            "smart_drive": meta.get("smart_drive", ""),
            "source": meta.get("source", ""),
            "content": c.content[:300] if c.content else "",
            "token_count": c.token_count,
            "created_at": c.created_at.isoformat() if c.created_at else "",
            "updated_at": c.updated_at.isoformat() if c.updated_at else "",
        })

    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/chunk-types")
def list_chunk_types(
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """返回已有的 chunk_type 枚举值。"""
    types = db.query(RagChunk.chunk_type).filter(
        RagChunk.is_deleted == False
    ).distinct().all()
    return [t[0] for t in types if t[0]]


@router.get("/brands")
def list_brands(
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """返回所有不重复的品牌列表（从 RagChunk 元数据提取）。"""
    brands = db.query(RagChunk.metadata_['brand'].astext).filter(
        RagChunk.is_deleted == False,
        RagChunk.metadata_['brand'].astext != ""
    ).distinct().all()
    return sorted([b[0] for b in brands if b[0]])


@router.get("/stats")
def document_stats(
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """知识库统计。"""
    from app.services.rag_service import rag_service
    return rag_service.get_stats(db)


@router.post("/import/json")
def import_json(
    body: dict,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_admin_user),
):
    """导入 JSON 车辆数据。"""
    from app.multi_agent.knowledge import KnowledgeAgent
    agent = KnowledgeAgent()
    result = agent.import_json(db, str(body))
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return {"status": "ok", **result.data}


@router.post("/import/csv")
async def import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_admin_user),
):
    """导入 CSV 文件。"""
    content = (await file.read()).decode("utf-8-sig")
    from app.multi_agent.knowledge import KnowledgeAgent
    agent = KnowledgeAgent()
    result = agent.import_csv(db, content)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return {"status": "ok", "filename": file.filename, **result.data}


@router.post("/import/text")
def import_text(
    body: dict,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_admin_user),
):
    """导入自由文本到知识库。"""
    content = body.get("content", "")
    if not content:
        raise HTTPException(status_code=400, detail="内容不能为空")
    from app.multi_agent.knowledge import KnowledgeAgent
    agent = KnowledgeAgent()
    result = agent.import_text(
        db, content,
        title=body.get("title"),
        brand=body.get("brand"),
        model=body.get("model"),
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return {"status": "ok", **result.data}


@router.get("/export/json")
def export_json(
    brand: str = Query(""),
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """导出知识库为 JSON。"""
    from app.multi_agent.knowledge import KnowledgeAgent
    agent = KnowledgeAgent()
    result = agent.export_json(db, brand or None)
    if not result.success:
        raise HTTPException(status_code=500, detail="导出失败")
    return {"status": "ok", "items": result.data, "count": len(result.data)}


@router.get("/export/markdown")
def export_markdown(
    doc_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """导出知识库为 Markdown 报告。"""
    from app.multi_agent.knowledge import KnowledgeAgent
    agent = KnowledgeAgent()
    result = agent.export_markdown(db, doc_id)
    if not result.success:
        raise HTTPException(status_code=500, detail="导出失败")
    return {"status": "ok", "markdown": result.data}


@router.get("/{chunk_id}")
def get_chunk(
    chunk_id: int,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """获取单条 RagChunk 详情。"""
    chunk = db.query(RagChunk).filter(
        RagChunk.id == chunk_id, RagChunk.is_deleted == False
    ).first()
    if not chunk:
        raise HTTPException(status_code=404, detail="区块不存在")
    meta = chunk.metadata_ or {}
    return {
        "id": chunk.id,
        "document_id": chunk.document_id,
        "chunk_id": chunk.chunk_id,
        "chunk_type": chunk.chunk_type,
        "chunk_index": chunk.chunk_index,
        "brand_name": meta.get("brand", ""),
        "model_name": meta.get("model", ""),
        "price_range": meta.get("price_range", ""),
        "year": meta.get("year", ""),
        "vehicle_type": meta.get("vehicle_type", ""),
        "power_type": meta.get("power_type", []),
        "smart_drive": meta.get("smart_drive", ""),
        "source": meta.get("source", ""),
        "content": chunk.content,
        "token_count": chunk.token_count,
        "created_at": chunk.created_at.isoformat() if chunk.created_at else "",
        "updated_at": chunk.updated_at.isoformat() if chunk.updated_at else "",
    }


@router.put("/{chunk_id}")
def update_chunk(
    chunk_id: int,
    body: dict,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_admin_user),
):
    """更新 RagChunk 的可编辑字段。"""
    chunk = db.query(RagChunk).filter(
        RagChunk.id == chunk_id, RagChunk.is_deleted == False
    ).first()
    if not chunk:
        raise HTTPException(status_code=404, detail="区块不存在")

    # 更新 chunk 自身的字段
    if "chunk_type" in body:
        chunk.chunk_type = body["chunk_type"]

    # 更新 metadata 中的字段
    meta = dict(chunk.metadata_ or {})
    for field in ("brand", "model", "price_range", "year", "vehicle_type", "source"):
        key = "brand_name" if field == "brand" else ("model_name" if field == "model" else field)
        if key in body:
            meta[field] = body[key]
    chunk.metadata_ = meta
    chunk.updated_at = datetime.now(timezone.utc)

    db.commit()
    return {"message": "更新成功"}


@router.delete("/{chunk_id}")
def delete_chunk(
    chunk_id: int,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_admin_user),
):
    """软删除 RagChunk。"""
    chunk = db.query(RagChunk).filter(
        RagChunk.id == chunk_id, RagChunk.is_deleted == False
    ).first()
    if not chunk:
        raise HTTPException(status_code=404, detail="区块不存在")
    chunk.is_deleted = True
    chunk.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "删除成功"}


@router.post("/batch-delete")
def batch_delete_chunks(
    ids: list[int],
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_admin_user),
):
    """批量软删除 RagChunk。"""
    count = db.query(RagChunk).filter(
        RagChunk.id.in_(ids), RagChunk.is_deleted == False
    ).update({"is_deleted": True, "deleted_at": datetime.now(timezone.utc)}, synchronize_session=False)
    db.commit()
    return {"message": f"成功删除 {count} 条数据"}
