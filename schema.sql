-- =========================================================
-- AutoMind AI 数据库结构（PostgreSQL + pgvector）
-- =========================================================
--
-- 使用方法：
--   1. 确保 PostgreSQL 14+ 已安装并运行
--   2. 创建数据库： CREATE DATABASE automind_db;
--   3. 执行此文件： psql -U <用户名> -d automind_db -f schema.sql
--
--   一键命令示例：
--   psql -U postgres -c "CREATE DATABASE automind_db;"
--   psql -U postgres -d automind_db -f schema.sql
--
-- 前置要求：
--   - PostgreSQL 14+
--   - pgvector 扩展已安装（https://github.com/pgvector/pgvector）
--
-- Schema 说明：
--   app     — 业务数据（用户、会话、消息、汽车价格、新闻）
--   rag     — 知识库（文档、分块、向量嵌入）
--   ops     — 运维日志（工具调用、RAG摄入、RAG检索）
--
-- 表清单（13 张）：
--   app.users                用户
--   app.chat_sessions        聊天会话
--   app.chat_messages        聊天消息
--   app.car_price_snapshots  汽车价格快照
--   app.news_articles        新闻文章
--   app.mcp_server_configs   MCP 服务器配置
--   rag.rag_documents        知识库文档
--   rag.rag_chunks           文档分块
--   rag.rag_chunk_embeddings 向量嵌入（1024维）
--   ops.tool_call_logs       工具调用日志
--   ops.rag_ingestion_jobs   RAG 摄入任务（预留）
--   ops.rag_retrieval_logs   RAG 检索日志（预留）
--
-- 设计约定：
--   - 所有表使用逻辑删除（is_deleted），不物理删除数据
--   - 所有表有 created_at / updated_at 时间戳
--   - update 触发器自动维护 updated_at
--   - 索引仅覆盖 is_deleted = FALSE 的行（部分索引）
--   - JSONB 字段使用 GIN 索引支持灵活查询
-- =========================================================

-- 1. 扩展与 Schema
CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS rag;
CREATE SCHEMA IF NOT EXISTS ops;


-- 2. 通用更新时间触发器函数
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- =========================================================
-- app.users
-- =========================================================
CREATE TABLE IF NOT EXISTS app.users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    email VARCHAR(255),
    password_hash TEXT,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    profile JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('active', 'inactive', 'blocked'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username_active
ON app.users(username)
WHERE is_deleted = FALSE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_active
ON app.users(email)
WHERE is_deleted = FALSE AND email IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_users_status_active
ON app.users(status)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_users_profile_gin
ON app.users USING GIN(profile);

DROP TRIGGER IF EXISTS trg_users_set_updated_at ON app.users;
CREATE TRIGGER trg_users_set_updated_at
BEFORE UPDATE ON app.users
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


-- =========================================================
-- app.chat_sessions
-- =========================================================
CREATE TABLE IF NOT EXISTS app.chat_sessions (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    user_id BIGINT NOT NULL REFERENCES app.users(id) ON DELETE CASCADE,
    title VARCHAR(200),
    summary TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('active', 'archived', 'closed'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_sessions_session_id_active
ON app.chat_sessions(session_id);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id_active
ON app.chat_sessions(user_id)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated_at_active
ON app.chat_sessions(updated_at DESC)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_chat_sessions_metadata_gin
ON app.chat_sessions USING GIN(metadata);

DROP TRIGGER IF EXISTS trg_chat_sessions_set_updated_at ON app.chat_sessions;
CREATE TRIGGER trg_chat_sessions_set_updated_at
BEFORE UPDATE ON app.chat_sessions
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


-- =========================================================
-- app.chat_messages
-- =========================================================
CREATE TABLE IF NOT EXISTS app.chat_messages (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL REFERENCES app.chat_sessions(session_id),
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    model_name VARCHAR(100),
    token_in INT,
    token_out INT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (role IN ('system', 'user', 'assistant', 'tool'))
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created_active
ON app.chat_messages(session_id, created_at)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_chat_messages_role_active
ON app.chat_messages(role)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_chat_messages_metadata_gin
ON app.chat_messages USING GIN(metadata);

DROP TRIGGER IF EXISTS trg_chat_messages_set_updated_at ON app.chat_messages;
CREATE TRIGGER trg_chat_messages_set_updated_at
BEFORE UPDATE ON app.chat_messages
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


-- =========================================================
-- ops.tool_call_logs
-- =========================================================
CREATE TABLE IF NOT EXISTS ops.tool_call_logs (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(100) REFERENCES app.chat_sessions(session_id),
    message_id BIGINT REFERENCES app.chat_messages(id) ON DELETE SET NULL,
    tool_name VARCHAR(100) NOT NULL,
    tool_input JSONB NOT NULL DEFAULT '{}'::jsonb,
    tool_output JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'success',
    error_text TEXT,
    latency_ms INT,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('success', 'failed', 'running'))
);

CREATE INDEX IF NOT EXISTS idx_tool_call_logs_session_id_active
ON ops.tool_call_logs(session_id)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_tool_call_logs_message_id_active
ON ops.tool_call_logs(message_id)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_tool_call_logs_tool_name_active
ON ops.tool_call_logs(tool_name)
WHERE is_deleted = FALSE;

DROP TRIGGER IF EXISTS trg_tool_call_logs_set_updated_at ON ops.tool_call_logs;
CREATE TRIGGER trg_tool_call_logs_set_updated_at
BEFORE UPDATE ON ops.tool_call_logs
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


-- =========================================================
-- app.car_price_snapshots
-- =========================================================
CREATE TABLE IF NOT EXISTS app.car_price_snapshots (
    id BIGSERIAL PRIMARY KEY,
    brand_name VARCHAR(100) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    version_name VARCHAR(150),
    price NUMERIC(12, 2) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'CNY',
    region VARCHAR(50),
    source VARCHAR(100),
    source_url TEXT,
    trend VARCHAR(20),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (price >= 0),
    CHECK (trend IS NULL OR trend IN ('up', 'down', 'stable'))
);

CREATE INDEX IF NOT EXISTS idx_car_price_snapshots_brand_model_time_active
ON app.car_price_snapshots(brand_name, model_name, created_at DESC)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_car_price_snapshots_source_active
ON app.car_price_snapshots(source)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_car_price_snapshots_metadata_gin
ON app.car_price_snapshots USING GIN(metadata);

DROP TRIGGER IF EXISTS trg_car_price_snapshots_set_updated_at ON app.car_price_snapshots;
CREATE TRIGGER trg_car_price_snapshots_set_updated_at
BEFORE UPDATE ON app.car_price_snapshots
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


-- =========================================================
-- app.news_articles
-- =========================================================
CREATE TABLE IF NOT EXISTS app.news_articles (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    summary TEXT,
    content TEXT,
    source VARCHAR(100),
    url TEXT NOT NULL,
    related_brand VARCHAR(100),
    published_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_news_articles_url_active
ON app.news_articles(url)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_news_articles_related_brand_active
ON app.news_articles(related_brand)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_news_articles_published_at_active
ON app.news_articles(published_at DESC)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_news_articles_metadata_gin
ON app.news_articles USING GIN(metadata);

DROP TRIGGER IF EXISTS trg_news_articles_set_updated_at ON app.news_articles;
CREATE TRIGGER trg_news_articles_set_updated_at
BEFORE UPDATE ON app.news_articles
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


-- =========================================================
-- app.mcp_server_configs
-- =========================================================
CREATE TABLE IF NOT EXISTS app.mcp_server_configs (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(500) NOT NULL DEFAULT '',
    transport VARCHAR(20) NOT NULL DEFAULT 'http',
    base_url VARCHAR(500) NOT NULL DEFAULT '',
    command VARCHAR(500) NOT NULL DEFAULT '',
    env_vars JSONB NOT NULL DEFAULT '{}'::jsonb,
    auth_type VARCHAR(20) NOT NULL DEFAULT 'none',
    auth_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    tool_schemas JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    is_essential BOOLEAN NOT NULL DEFAULT FALSE,
    timeout_seconds INT NOT NULL DEFAULT 30,
    max_retries INT NOT NULL DEFAULT 2,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (transport IN ('http', 'stdio', 'sse')),
    CHECK (auth_type IN ('none', 'bearer', 'api_key', 'oauth2'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_mcp_server_configs_name_active
ON app.mcp_server_configs(name)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_mcp_server_configs_enabled_active
ON app.mcp_server_configs(is_enabled)
WHERE is_deleted = FALSE;

DROP TRIGGER IF EXISTS trg_mcp_server_configs_set_updated_at ON app.mcp_server_configs;
CREATE TRIGGER trg_mcp_server_configs_set_updated_at
BEFORE UPDATE ON app.mcp_server_configs
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


-- =========================================================
-- rag.rag_documents
-- =========================================================
CREATE TABLE IF NOT EXISTS rag.rag_documents (
    id BIGSERIAL PRIMARY KEY,
    source_type VARCHAR(50) NOT NULL,
    source_uri TEXT,
    title VARCHAR(500),
    owner_user_id BIGINT REFERENCES app.users(id) ON DELETE SET NULL,
    content_hash VARCHAR(64),
    doc_status VARCHAR(20) NOT NULL DEFAULT 'ready',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (doc_status IN ('pending', 'processing', 'ready', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_rag_documents_owner_user_id_active
ON rag.rag_documents(owner_user_id)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_rag_documents_source_type_active
ON rag.rag_documents(source_type)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_rag_documents_content_hash_active
ON rag.rag_documents(content_hash)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_rag_documents_metadata_gin
ON rag.rag_documents USING GIN(metadata);

DROP TRIGGER IF EXISTS trg_rag_documents_set_updated_at ON rag.rag_documents;
CREATE TRIGGER trg_rag_documents_set_updated_at
BEFORE UPDATE ON rag.rag_documents
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

-- Migration: ensure metadata columns are JSONB (not plain JSON)
DO $$ BEGIN
    ALTER TABLE rag.rag_documents
        ALTER COLUMN metadata TYPE JSONB USING metadata::jsonb;
EXCEPTION WHEN others THEN
    RAISE NOTICE 'rag.rag_documents.metadata migration skipped: %', SQLERRM;
END $$;


-- =========================================================
-- rag.rag_chunks
-- =========================================================
CREATE TABLE IF NOT EXISTS rag.rag_chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES rag.rag_documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    chunk_id VARCHAR(200),
    chunk_type VARCHAR(20) NOT NULL DEFAULT 'model',
    content TEXT NOT NULL,
    token_count INT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_rag_chunks_document_chunk_active
ON rag.rag_chunks(document_id, chunk_index)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_rag_chunks_document_id_active
ON rag.rag_chunks(document_id)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_rag_chunks_metadata_gin
ON rag.rag_chunks USING GIN(metadata);

DROP TRIGGER IF EXISTS trg_rag_chunks_set_updated_at ON rag.rag_chunks;
CREATE TRIGGER trg_rag_chunks_set_updated_at
BEFORE UPDATE ON rag.rag_chunks
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

-- Migration: ensure metadata columns are JSONB (not plain JSON)
DO $$ BEGIN
    ALTER TABLE rag.rag_chunks
        ALTER COLUMN metadata TYPE JSONB USING metadata::jsonb;
EXCEPTION WHEN others THEN
    RAISE NOTICE 'rag.rag_chunks.metadata migration skipped: %', SQLERRM;
END $$;


-- =========================================================
-- rag.rag_chunk_embeddings
-- 当前向量维度：1024
-- =========================================================
CREATE TABLE IF NOT EXISTS rag.rag_chunk_embeddings (
    id BIGSERIAL PRIMARY KEY,
    chunk_id BIGINT NOT NULL REFERENCES rag.rag_chunks(id) ON DELETE CASCADE,
    embedding_model VARCHAR(100) NOT NULL,
    embedding VECTOR(1024) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_rag_chunk_embeddings_chunk_model_active
ON rag.rag_chunk_embeddings(chunk_id, embedding_model)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_rag_chunk_embeddings_chunk_id_active
ON rag.rag_chunk_embeddings(chunk_id)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_rag_chunk_embeddings_metadata_gin
ON rag.rag_chunk_embeddings USING GIN(metadata);

CREATE INDEX IF NOT EXISTS idx_rag_chunk_embeddings_hnsw_active
ON rag.rag_chunk_embeddings
USING hnsw (embedding vector_cosine_ops);

DROP TRIGGER IF EXISTS trg_rag_chunk_embeddings_set_updated_at ON rag.rag_chunk_embeddings;
CREATE TRIGGER trg_rag_chunk_embeddings_set_updated_at
BEFORE UPDATE ON rag.rag_chunk_embeddings
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


-- =========================================================
-- ops.rag_ingestion_jobs
-- =========================================================
CREATE TABLE IF NOT EXISTS ops.rag_ingestion_jobs (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT REFERENCES rag.rag_documents(id) ON DELETE CASCADE,
    source_type VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    step VARCHAR(50),
    error_text TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('pending', 'running', 'success', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_rag_ingestion_jobs_document_id_active
ON ops.rag_ingestion_jobs(document_id)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_rag_ingestion_jobs_status_active
ON ops.rag_ingestion_jobs(status)
WHERE is_deleted = FALSE;

DROP TRIGGER IF EXISTS trg_rag_ingestion_jobs_set_updated_at ON ops.rag_ingestion_jobs;
CREATE TRIGGER trg_rag_ingestion_jobs_set_updated_at
BEFORE UPDATE ON ops.rag_ingestion_jobs
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


-- =========================================================
-- ops.rag_retrieval_logs
-- =========================================================
CREATE TABLE IF NOT EXISTS ops.rag_retrieval_logs (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(100) REFERENCES app.chat_sessions(session_id),
    query_text TEXT NOT NULL,
    retrieval_strategy VARCHAR(50) NOT NULL DEFAULT 'vector',
    top_k INT NOT NULL DEFAULT 5,
    filters JSONB NOT NULL DEFAULT '{}'::jsonb,
    results JSONB NOT NULL DEFAULT '[]'::jsonb,
    latency_ms INT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (retrieval_strategy IN ('vector', 'hybrid', 'keyword'))
);

CREATE INDEX IF NOT EXISTS idx_rag_retrieval_logs_session_id_active
ON ops.rag_retrieval_logs(session_id)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_rag_retrieval_logs_created_at_active
ON ops.rag_retrieval_logs(created_at DESC)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_rag_retrieval_logs_filters_gin
ON ops.rag_retrieval_logs USING GIN(filters);

CREATE INDEX IF NOT EXISTS idx_rag_retrieval_logs_results_gin
ON ops.rag_retrieval_logs USING GIN(results);

DROP TRIGGER IF EXISTS trg_rag_retrieval_logs_set_updated_at ON ops.rag_retrieval_logs;
CREATE TRIGGER trg_rag_retrieval_logs_set_updated_at
BEFORE UPDATE ON ops.rag_retrieval_logs
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();
