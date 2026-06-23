

"""
AutoMind AI - FastAPI 应用入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text
import bcrypt

from app.core.config import settings
from app.core.logging import logger
from app.db.database import engine, Base, SessionLocal
from app.db.models import User
from app.api.chat import router as chat_router
from app.api.auth import router as auth_router
from app.api.data import router as data_router
from app.api.admin import router as admin_router
from app.api.rag import router as rag_router

ADMIN_PERMISSIONS = [
    "user:read", "user:create", "user:update", "user:delete",
    "data:read", "data:create", "data:update", "data:delete",
    "session:read", "session:delete",
    "system:config",
]

ADMIN_PROFILE = {
    "display_name": "系统管理员",
    "permissions": ADMIN_PERMISSIONS,
    
}


def _hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _seed_admin():
    """创建默认管理员账户（如果不存在）；如果是旧格式密码则更新为 bcrypt"""
    db = SessionLocal()
    try:
        existing = db.query(User).filter(
            User.username == "admin",
            User.is_deleted == False,
        ).first()
        if existing:
            if existing.password_hash and not existing.password_hash.startswith("$2"):
                existing.password_hash = _hash_pw("admin")
                existing.role = "admin"
                existing.profile = ADMIN_PROFILE
                db.commit()
                logger.info("Admin password upgraded to bcrypt")
            return
        admin = User(
            username="admin",
            email="admin@automind.local",
            password_hash=_hash_pw("admin"),
            role="admin",
            status="active",
            profile=ADMIN_PROFILE,
        )
        db.add(admin)
        db.commit()
        logger.info("Default admin user created (username: admin, password: admin)")
    except Exception as e:
        db.rollback()
        logger.warning(f"Seed admin skipped: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AutoMind AI application...")
    # 确保 PostgreSQL schema 存在
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS app"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS ops"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS rag"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    # 补齐旧表缺少的列
    with engine.connect() as conn:
        cols = [row[0] for row in conn.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_schema='app' AND table_name='users'")
        ).fetchall()]
        if "role" not in cols:
            conn.execute(text("ALTER TABLE app.users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"))
            conn.commit()
            logger.info("Added missing column: app.users.role")
        # Module 2: add chunk_type to rag_chunks for structured chunking
        rag_cols = [row[0] for row in conn.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_schema='rag' AND table_name='rag_chunks'")
        ).fetchall()]
        if "chunk_type" not in rag_cols:
            conn.execute(text("ALTER TABLE rag.rag_chunks ADD COLUMN chunk_type VARCHAR(20) NOT NULL DEFAULT 'model'"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_rag_chunks_chunk_type ON rag.rag_chunks(chunk_type)"))
            conn.commit()
            logger.info("Added missing column: rag.rag_chunks.chunk_type")
    logger.info("Database tables created")
    _seed_admin()

    yield
    logger.info("Shutting down AutoMind AI application...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="智能汽车价格分析助手",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(chat_router, prefix=settings.API_V1_PREFIX)
app.include_router(data_router, prefix=settings.API_V1_PREFIX)
app.include_router(admin_router, prefix=settings.API_V1_PREFIX)
app.include_router(rag_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
def root():
    return {
        "message": "Welcome to AutoMind AI",
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=settings.DEBUG)
