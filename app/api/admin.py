"""
后台管理 API - 用户管理 + 仪表盘统计 + LLM配置
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.database import get_db
from app.db.models import User, ChatSession, ChatMessage, CarPriceSnapshot
from app.auth.dependencies import admin_required
from app.services.llm_config_service import get_current_config, update_config, switch_model, test_connection
from app.core.logging import logger

router = APIRouter(
    prefix="/admin",
    tags=["后台管理"],
    dependencies=[Depends(admin_required)],
)


# ── 仪表盘统计 ──────────────────────────────────────────

@router.get("/stats")
def dashboard_stats(db: Session = Depends(get_db)):
    now = func.now()
    total_users = db.query(func.count(User.id)).filter(User.is_deleted == False).scalar() or 0
    total_sessions = db.query(func.count(ChatSession.id)).filter(ChatSession.is_deleted == False).scalar() or 0
    total_messages = db.query(func.count(ChatMessage.id)).filter(ChatMessage.is_deleted == False).scalar() or 0
    total_data = db.query(func.count(CarPriceSnapshot.id)).filter(CarPriceSnapshot.is_deleted == False).scalar() or 0

    new_users_today = (
        db.query(func.count(User.id))
        .filter(User.is_deleted == False, func.date(User.created_at) == func.date(now))
        .scalar() or 0
    )
    new_sessions_today = (
        db.query(func.count(ChatSession.id))
        .filter(ChatSession.is_deleted == False, func.date(ChatSession.created_at) == func.date(now))
        .scalar() or 0
    )

    return {
        "total_users": total_users,
        "total_sessions": total_sessions,
        "total_messages": total_messages,
        "total_data": total_data,
        "new_users_today": new_users_today,
        "new_sessions_today": new_sessions_today,
    }


@router.get("/trend")
def message_trend(days: int = Query(7, ge=1, le=90), db: Session = Depends(get_db)):
    rows = (
        db.query(
            func.date(ChatMessage.created_at).label("day"),
            func.count(ChatMessage.id).label("cnt"),
        )
        .filter(ChatMessage.is_deleted == False)
        .group_by(func.date(ChatMessage.created_at))
        .order_by(func.date(ChatMessage.created_at).desc())
        .limit(days)
        .all()
    )
    return [{"date": str(r.day), "count": r.cnt} for r in reversed(rows)]


@router.get("/activity")
def recent_activity(limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.is_deleted == False)
        .order_by(ChatSession.updated_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "session_id": s.session_id,
            "title": s.title or "未命名会话",
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in sessions
    ]


# ── 用户管理 CRUD ────────────────────────────────────────

@router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: str = Query(""),
    role: str = Query(""),
    status: str = Query(""),
    db: Session = Depends(get_db),
    ):
    query = db.query(User).filter(User.is_deleted == False)

    if keyword:
        like = f"%{keyword}%"
        query = query.filter((User.username.ilike(like)) | (User.email.ilike(like)))
    if role:
        query = query.filter(User.role == role)
    if status:
        query = query.filter(User.status == status)

    total = query.count()
    items = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "role": u.role,
                "status": u.status,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "updated_at": u.updated_at.isoformat() if u.updated_at else None,
            }
            for u in items
        ],
    }


@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    body: dict,
    db: Session = Depends(get_db),
    ):
    new_role = body.get("role")
    if new_role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="无效的角色")
    user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.role = new_role
    db.commit()
    logger.info(f"User {user.username} role changed to {new_role}")
    return {"message": f"用户角色已更新为 {new_role}"}


@router.put("/users/{user_id}/status")
def toggle_user_status(
    user_id: int,
    db: Session = Depends(get_db),
    ):
    user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="不能禁用管理员账户")
    user.status = "disabled" if user.status == "active" else "active"
    db.commit()
    logger.info(f"User {user.username} status toggled to {user.status}")
    return {"message": f"用户状态已更新为 {user.status}"}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    ):
    user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="不能删除管理员账户")
    user.is_deleted = True
    db.commit()
    logger.info(f"User {user.username} soft-deleted")
    return {"message": "用户已删除"}


# ── LLM 配置管理 ──────────────────────────────────────────

@router.get("/llm-config")
def get_llm_config():
    """获取当前 LLM 配置（API Key 脱敏）"""
    return get_current_config()


@router.put("/llm-config")
def update_llm_config(body: dict):
    """更新 LLM 配置，持久化到 .env 并重初始化 LLM 服务"""
    try:
        return update_config(body)
    except Exception as exc:
        logger.error(f"Failed to update LLM config: {exc}")
        raise HTTPException(status_code=500, detail="配置更新失败，请稍后重试")


@router.post("/llm-config/test")
def test_llm_connection(body: dict):
    """测试 LLM 后端连接"""
    backend = body.get("backend")
    if backend not in ("cloud", "local"):
        raise HTTPException(status_code=400, detail="backend 必须是 'cloud' 或 'local'")
    return test_connection(
        backend=backend,
        api_key=body.get("api_key"),
        base_url=body.get("base_url"),
        model_name=body.get("model_name"),
    )


@router.put("/llm-config/switch")
def switch_llm_model(body: dict):
    """切换默认模型 (primary / assistant)"""
    model_type = body.get("model_type")
    if model_type not in ("primary", "assistant"):
        raise HTTPException(status_code=400, detail="model_type 必须是 'primary' 或 'assistant'")
    result = switch_model(model_type)
    return {"message": f"已切换至 {model_type} 模型", **result}
