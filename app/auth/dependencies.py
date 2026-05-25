"""
FastAPI dependencies for authentication and authorization.
"""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User
from app.auth.jwt import decode_access_token


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Extract and validate the current user from the JWT Bearer token.

    Raises 401 if the token is missing, invalid, expired, or the user does not exist.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供有效的认证令牌")
    token = auth_header[7:]
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="令牌无效或已过期")
    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="令牌无效")
    user = db.query(User).filter(
        User.id == user_id,
        User.is_deleted == False,
    ).first()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


def admin_required(current_user: User = Depends(get_current_user)) -> User:
    """Require the current user to have the 'admin' role.

    Raises 403 if the user is not an admin.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user
