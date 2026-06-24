"""
数据管理 API — 基于 RAG 知识库的区块（chunks）管理
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import RagDocument, RagChunk
from app.api.auth import get_current_admin_user, get_current_user
from app.core.logging import logger

router = APIRouter(prefix="/data", tags=["数据管理"])

# --- 序列化 & 字段映射 ---

# API 字段名 → metadata JSON 字段名
_FIELD_KEY_MAP: dict[str, str] = {"brand_name": "brand", "model_name": "model"}


class UpdateChunkRequest(BaseModel):
    """RagChunk 可编辑字段。"""
    chunk_type: str | None = None
    brand_name: str | None = Field(None, description="品牌名 → metadata.brand")
    model_name: str | None = Field(None, description="车型名 → metadata.model")
    price_range: str | None = None
    year: str | None = None
    vehicle_type: str | None = None
    power_type: list[str] | None = Field(None, description="动力类型列表 → metadata.power_type")
    smart_drive: str | None = Field(None, description="智驾等级 → metadata.smart_drive")
    source: str | None = None


def _chunk_to_item(chunk: RagChunk, *, include_full_content: bool = False) -> dict:
    """将 RagChunk ORM 对象序列化为 API 响应 dict。"""
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
        "content": chunk.content
        if include_full_content
        else (chunk.content[:300] if chunk.content else ""),
        "token_count": chunk.token_count,
        "created_at": chunk.created_at.isoformat() if chunk.created_at else "",
        "updated_at": chunk.updated_at.isoformat() if chunk.updated_at else "",
    }


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
            | (func.jsonb_extract_path_text(RagChunk.metadata_, 'brand').ilike(like))
            | (func.jsonb_extract_path_text(RagChunk.metadata_, 'model').ilike(like))
        )
    if brand:
        query = query.filter(
            func.lower(func.jsonb_extract_path_text(RagChunk.metadata_, 'brand')) == brand.lower()
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

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_chunk_to_item(c) for c in chunks],
    }


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
    brands = db.query(func.jsonb_extract_path_text(RagChunk.metadata_, 'brand')).filter(
        RagChunk.is_deleted == False,
        func.jsonb_extract_path_text(RagChunk.metadata_, 'brand') != ""
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
    return _chunk_to_item(chunk, include_full_content=True)


@router.put("/{chunk_id}")
def update_chunk(
    chunk_id: int,
    body: UpdateChunkRequest,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_admin_user),
):
    """更新 RagChunk 的可编辑字段。"""
    chunk = db.query(RagChunk).filter(
        RagChunk.id == chunk_id, RagChunk.is_deleted == False
    ).first()
    if not chunk:
        raise HTTPException(status_code=404, detail="区块不存在")

    body_dict = body.model_dump(exclude_unset=True)

    # 更新 chunk 自身的字段
    if "chunk_type" in body_dict:
        chunk.chunk_type = body_dict.pop("chunk_type")

    # 更新 metadata JSON 字段 — 先做 API→DB 名称映射
    meta = dict(chunk.metadata_ or {})
    for api_field, meta_field in _FIELD_KEY_MAP.items():
        if api_field in body_dict:
            meta[meta_field] = body_dict.pop(api_field)
    # 剩余同名字段直接写入 metadata
    for field in ("price_range", "year", "vehicle_type", "power_type", "smart_drive", "source"):
        if field in body_dict:
            meta[field] = body_dict.pop(field)

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
