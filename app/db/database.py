"""
数据库连接配置（PostgreSQL）
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={
        "options": "-c client_encoding=UTF8",
        "client_encoding": "UTF8",
    },
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI 依赖：获取并释放一个数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
