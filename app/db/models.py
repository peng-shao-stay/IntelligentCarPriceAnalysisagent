"""
数据库模型定义
"""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, ForeignKey,
    Boolean, BigInteger, Numeric, JSON, CheckConstraint,
)
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.db.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


# ============================================================
# app schema tables
# ============================================================

class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "app"}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False)
    email = Column(String(255))
    password_hash = Column(Text)
    role = Column(String(20), nullable=False, default="user")
    status = Column(String(20), nullable=False, default="active")
    profile = Column(JSON, nullable=False, default=dict)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    chat_sessions = relationship("ChatSession", back_populates="user")


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = {"schema": "app"}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False)
    user_id = Column(BigInteger, ForeignKey("app.users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200))
    summary = Column(Text)
    status = Column(String(20), nullable=False, default="active")
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = {"schema": "app"}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String(100), ForeignKey("app.chat_sessions.session_id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    model_name = Column(String(100))
    token_in = Column(Integer)
    token_out = Column(Integer)
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    session = relationship("ChatSession", back_populates="messages")


class CarPriceSnapshot(Base):
    __tablename__ = "car_price_snapshots"
    __table_args__ = (
        CheckConstraint("price >= 0"),
        {"schema": "app"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    brand_name = Column(String(100), nullable=False)
    model_name = Column(String(100), nullable=False)
    version_name = Column(String(150))
    price = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="CNY")
    region = Column(String(50))
    source = Column(String(100))
    source_url = Column(Text)
    trend = Column(String(20))
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


class NewsArticle(Base):
    __tablename__ = "news_articles"
    __table_args__ = {"schema": "app"}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    summary = Column(Text)
    content = Column(Text)
    source = Column(String(100))
    url = Column(Text, nullable=False)
    related_brand = Column(String(100))
    published_at = Column(DateTime(timezone=True))
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


class MCPServerConfig(Base):
    __tablename__ = "mcp_server_configs"
    __table_args__ = {"schema": "app"}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), default="")
    transport = Column(String(20), nullable=False, default="http")
    base_url = Column(String(500), default="")
    command = Column(String(500), default="")
    env_vars = Column(JSON, nullable=False, default=dict)
    auth_type = Column(String(20), nullable=False, default="none")
    auth_config = Column(JSON, nullable=False, default=dict)
    tool_schemas = Column(JSON, nullable=False, default=list)
    is_enabled = Column(Boolean, nullable=False, default=True)
    is_essential = Column(Boolean, nullable=False, default=False)
    timeout_seconds = Column(Integer, nullable=False, default=30)
    max_retries = Column(Integer, nullable=False, default=2)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


# ============================================================
# ops schema tables
# ============================================================

class ToolCallLog(Base):
    __tablename__ = "tool_call_logs"
    __table_args__ = {"schema": "ops"}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String(100), ForeignKey("app.chat_sessions.session_id"))
    message_id = Column(BigInteger, ForeignKey("app.chat_messages.id", ondelete="SET NULL"))
    tool_name = Column(String(100), nullable=False)
    tool_input = Column(JSON, nullable=False, default=dict)
    tool_output = Column(JSON, nullable=False, default=dict)
    status = Column(String(20), nullable=False, default="success")
    error_text = Column(Text)
    latency_ms = Column(Integer)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


class RagIngestionJob(Base):
    """RAG document ingestion job log (reserved for future use)."""
    __tablename__ = "rag_ingestion_jobs"
    __table_args__ = {"schema": "ops"}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    document_id = Column(BigInteger, ForeignKey("rag.rag_documents.id", ondelete="CASCADE"))
    source_type = Column(String(50))
    status = Column(String(20), nullable=False, default="pending")
    step = Column(String(50))
    error_text = Column(Text)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


class RagRetrievalLog(Base):
    """RAG retrieval query log (reserved for future use)."""
    __tablename__ = "rag_retrieval_logs"
    __table_args__ = {"schema": "ops"}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String(100), ForeignKey("app.chat_sessions.session_id"))
    query_text = Column(Text, nullable=False)
    retrieval_strategy = Column(String(50), nullable=False, default="vector")
    top_k = Column(Integer, nullable=False, default=5)
    filters = Column(JSON, nullable=False, default=dict)
    results = Column(JSON, nullable=False, default=list)
    latency_ms = Column(Integer)
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


# ============================================================
# rag schema tables
# ============================================================

class RagDocument(Base):
    __tablename__ = "rag_documents"
    __table_args__ = {"schema": "rag"}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_type = Column(String(50), nullable=False)
    source_uri = Column(Text)
    title = Column(String(500))
    owner_user_id = Column(BigInteger, ForeignKey("app.users.id", ondelete="SET NULL"))
    content_hash = Column(String(64))
    doc_status = Column(String(20), nullable=False, default="ready")
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


class RagChunk(Base):
    __tablename__ = "rag_chunks"
    __table_args__ = (
        # GIN index on metadata JSONB for fast brand/model/topic filtering
        {"schema": "rag"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    document_id = Column(BigInteger, ForeignKey("rag.rag_documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_id = Column(String(200), nullable=True, index=True,
                      comment="Structured chunk ID e.g. model:tesla:model3:2024")
    chunk_type = Column(String(20), nullable=False, default="model", index=True,
                        comment="brand | model | feature | comparison")
    content = Column(Text, nullable=False)
    token_count = Column(Integer)
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


class RagChunkEmbedding(Base):
    __tablename__ = "rag_chunk_embeddings"
    __table_args__ = {"schema": "rag"}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    chunk_id = Column(BigInteger, ForeignKey("rag.rag_chunks.id", ondelete="CASCADE"), nullable=False)
    embedding_model = Column(String(100), nullable=False)
    embedding = Column(Vector(1024), nullable=False)
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
