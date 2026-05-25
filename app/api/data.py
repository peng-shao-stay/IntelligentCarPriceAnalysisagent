"""
文档管理 API — 基于 RAG 知识库的文档导入/导出/管理
替代旧的 CarPriceSnapshot CRUD（已废弃）
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.db.models import RagDocument
from app.api.auth import get_current_admin_user, get_current_user
from app.core.logging import logger

router = APIRouter(prefix="/data", tags=["数据管理"])


@router.get("/list")
def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    brand: str = Query(""),
    keyword: str = Query(""),
    source_type: str = Query(""),
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """列出知识库文档（替代旧的 CarPriceSnapshot 列表）。"""
    query = db.query(RagDocument).filter(RagDocument.is_deleted == False)

    if source_type:
        query = query.filter(RagDocument.source_type == source_type)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            (RagDocument.title.ilike(like))
            | (RagDocument.source_uri.ilike(like))
        )
    if brand:
        from sqlalchemy import func
        query = query.filter(
            func.lower(func.jsonb_extract_path_text(RagDocument.metadata_, "brand"))
            == brand.lower()
        )

    total = query.count()
    docs = query.order_by(RagDocument.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    items = []
    for d in docs:
        items.append({
            "id": d.id,
            "title": d.title,
            "source_type": d.source_type,
            "brand": d.metadata_.get("brand", ""),
            "model": d.metadata_.get("model", ""),
            "year": d.metadata_.get("year", ""),
            "created_at": d.created_at.isoformat() if d.created_at else "",
        })

    return {"total": total, "page": page, "page_size": page_size, "items": items}


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


@router.delete("/{doc_id}")
def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_admin_user),
):
    """删除知识库文档。"""
    from app.services.rag_service import rag_service
    success = rag_service.delete_document(db, doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"message": "删除成功"}
