"""
用户认证 API 路由
"""
import time
import base64
from io import BytesIO
import uuid
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import bcrypt
from PIL import Image, ImageDraw, ImageFont

from app.db.database import get_db
from app.db.models import User
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    CaptchaResponse,
    LoginResponse,
    UserInfo,
    TokenVerifyRequest,
)
from app.auth.jwt import create_access_token, decode_access_token
from app.auth.dependencies import get_current_user, admin_required as _admin_required
from app.core.logging import logger


# Backward-compatible re-exports for modules that import from app.api.auth
def get_current_admin_user(
    current_user=Depends(_admin_required),
):
    return current_user


def require_permission(permission: str):
    def checker(current_user=Depends(get_current_user)):
        profile = current_user.profile or {}
        permissions: list = profile.get("permissions", [])
        if current_user.role == "admin":
            return current_user
        if permission not in permissions:
            raise HTTPException(status_code=403, detail=f"缺少权限: {permission}")
        return current_user
    return checker

router = APIRouter(prefix="/auth", tags=["认证"])

captcha_store: dict[str, dict] = {}


def _get_captcha_redis():
    """Try to get Redis client for captcha storage (multi-worker safe)."""
    try:
        from app.memory.redis_memory import memory_manager
        if memory_manager.available:
            return memory_manager._redis
    except Exception:
        pass
    return None


def _captcha_set(captcha_id: str, data: dict, ttl: int = 300) -> None:
    redis_conn = _get_captcha_redis()
    if redis_conn:
        try:
            import json
            redis_conn.setex(
                f"captcha:{captcha_id}", ttl,
                json.dumps(data, ensure_ascii=False)
            )
            return
        except Exception:
            pass
    captcha_store[captcha_id] = data


def _captcha_get_and_delete(captcha_id: str) -> dict | None:
    redis_conn = _get_captcha_redis()
    if redis_conn:
        try:
            import json
            key = f"captcha:{captcha_id}"
            raw = redis_conn.get(key)
            if raw:
                redis_conn.delete(key)
                return json.loads(raw)
        except Exception:
            pass
    return captcha_store.pop(captcha_id, None)


def _clean_expired_captchas():
    """Clean expired in-memory captchas. Redis captchas auto-expire via TTL."""
    now = time.time()
    expired = [cid for cid, v in captcha_store.items() if now - v["created_at"] > 300]
    for cid in expired:
        del captcha_store[cid]


def generate_captcha_image(text: str) -> str:
    width, height = 120, 50
    image = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        except OSError:
            font = ImageFont.load_default()

    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    x = (width - text_width) // 2
    y = (height - text_height) // 2

    for i, char in enumerate(text):
        color = (secrets.randbelow(150), secrets.randbelow(150), secrets.randbelow(150))
        draw.text((x + i * 25, y), char, fill=color, font=font)

    for _ in range(5):
        x1, y1 = secrets.randbelow(width), secrets.randbelow(height)
        x2, y2 = secrets.randbelow(width), secrets.randbelow(height)
        color = (secrets.randbelow(200), secrets.randbelow(200), secrets.randbelow(200))
        draw.line([(x1, y1), (x2, y2)], fill=color, width=1)

    for _ in range(50):
        x, y = secrets.randbelow(width), secrets.randbelow(height)
        color = (secrets.randbelow(200), secrets.randbelow(200), secrets.randbelow(200))
        draw.point((x, y), fill=color)

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}"


@router.get("/captcha", response_model=CaptchaResponse)
def get_captcha():
    _clean_expired_captchas()
    try:
        captcha_text = "".join([str(secrets.randbelow(10)) for _ in range(4)])
        captcha_id = str(uuid.uuid4())
        _captcha_set(captcha_id, {"text": captcha_text, "created_at": time.time()})
        captcha_image = generate_captcha_image(captcha_text)
        logger.info(f"Generated captcha: {captcha_id}")
        return CaptchaResponse(captcha_id=captcha_id, captcha_image=captcha_image)
    except Exception as e:
        logger.error(f"Generate captcha error: {str(e)}")
        raise HTTPException(status_code=500, detail="生成验证码失败")


@router.post("/register", response_model=LoginResponse)
def register(request: UserRegisterRequest, db: Session = Depends(get_db)):
    try:
        existing_user = db.query(User).filter(
            User.username == request.username,
            User.is_deleted == False,
        ).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="用户名已存在")

        if request.email:
            existing_email = db.query(User).filter(
                User.email == request.email,
                User.is_deleted == False,
            ).first()
            if existing_email:
                raise HTTPException(status_code=400, detail="邮箱已被注册")

        new_user = User(
            username=request.username,
            email=request.email,
            password_hash=bcrypt.hashpw(request.password.encode(), bcrypt.gensalt()).decode(),
            role="user",
            status="active",
            profile={"display_name": request.username, "permissions": ["data:read"]},
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        token = create_access_token(new_user.id, new_user.role)

        logger.info(f"User registered: {request.username}")
        return LoginResponse(
            success=True,
            message="注册成功",
            user_id=new_user.id,
            username=new_user.username,
            token=token,
            role=new_user.role,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Register error: {str(e)}")
        raise HTTPException(status_code=500, detail="注册失败")


@router.post("/login", response_model=LoginResponse)
def login(request: UserLoginRequest, db: Session = Depends(get_db)):
    try:
        _clean_expired_captchas()

        if not request.captcha_id:
            raise HTTPException(status_code=400, detail="缺少验证码ID")
        if not request.captcha:
            raise HTTPException(status_code=400, detail="缺少验证码")
        data = _captcha_get_and_delete(request.captcha_id)
        if not data or data["text"] != request.captcha or time.time() - data["created_at"] > 300:
            raise HTTPException(status_code=400, detail="验证码错误或已过期")

        user = db.query(User).filter(
            (User.username == request.account) | (User.email == request.account),
            User.is_deleted == False,
        ).first()

        if not user or not user.password_hash:
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        if not bcrypt.checkpw(request.password.encode(), user.password_hash.encode()):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        token = create_access_token(user.id, user.role)

        logger.info(f"User logged in: {user.username}")
        return LoginResponse(
            success=True,
            message="登录成功",
            user_id=user.id,
            username=user.username,
            token=token,
            role=user.role,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="登录失败")


@router.post("/verify-token")
def verify_token(request: TokenVerifyRequest):
    """Verify a JWT token. Accepts token in POST body (not query param)."""
    payload = decode_access_token(request.token)
    if payload is None:
        raise HTTPException(status_code=401, detail="令牌无效或已过期")
    return {
        "valid": True,
        "user_id": payload.get("user_id"),
        "role": payload.get("role"),
    }


@router.get("/me", response_model=UserInfo)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
