#!/bin/bash
# ============================================
# AutoMind AI - Docker 启动脚本
# 等待 PostgreSQL + Redis 就绪，确保 pgvector 扩展
# ============================================
set -e

echo "============================================"
echo " AutoMind AI - Docker Entrypoint"
echo "============================================"

# --- 等待 PostgreSQL ---
echo "[1/3] Waiting for PostgreSQL..."
until python -c "
import os, sys
from urllib.parse import urlparse

url = urlparse(os.environ.get('DATABASE_URL', ''))
try:
    import psycopg2
    conn = psycopg2.connect(
        host=url.hostname,
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        dbname=url.path.lstrip('/'),
        connect_timeout=3,
    )
    conn.close()
    sys.exit(0)
except Exception as e:
    sys.exit(1)
" 2>/dev/null; do
    echo "   PostgreSQL unavailable - retrying in 2s..."
    sleep 2
done
echo "   PostgreSQL is ready."

# --- 等待 Redis ---
echo "[2/3] Waiting for Redis..."
until python -c "
import os, sys
try:
    import redis
    r = redis.from_url(os.environ.get('REDIS_URL', 'redis://redis:6379/0'))
    r.ping()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; do
    echo "   Redis unavailable - retrying in 2s..."
    sleep 2
done
echo "   Redis is ready."

# --- 确保 pgvector 扩展 ---
echo "[3/3] Ensuring pgvector extension..."
python -c "
from app.db.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
    conn.commit()
"
echo "   pgvector extension ensured."

echo "============================================"
echo " All dependencies ready. Starting app..."
echo "============================================"

exec "$@"
