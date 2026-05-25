# rag/ — RAG 服务模块规范

> `app/services/rag_service.py` 是 RAG 核心实现。
> 此目录规范描述了 RAG 相关代码的组织约定。

## 核心流程

```
文档上传 → chunking (app/utils/chunking.py)
         → embedding (LLM API)
         → 存储 (pgvector, app/db/models.py)
         → 检索 (app/services/rag_service.py)
         → 上下文注入 (app/agent/context.py)
```

## 模块职责

| 模块 | 文件 | 职责 |
|------|------|------|
| 分块器 | `app/utils/chunking.py` | 文档切片、品牌/型号提取 |
| RAG 服务 | `app/services/rag_service.py` | 向量搜索、上下文构建、文档录入 |
| RAG API | `app/api/rag.py` | REST 接口：搜索、录入、统计 |
| RAG MCP | `mcp_servers/rag_server.py` | MCP 协议接入 RAG 服务 |
| 数据模型 | `app/schemas/chunk.py` | RAGChunk Pydantic 模型 |
| DB 模型 | `app/db/models.py` | RAGDocument、RAGChunk ORM 模型 |

## 数据库 Schema

使用 PostgreSQL `rag` schema：

```sql
CREATE SCHEMA IF NOT EXISTS rag;

CREATE TABLE rag.rag_documents (...);
CREATE TABLE rag.rag_chunks (...);  -- 含 embedding vector(1536)
```

## 分块策略

- 默认 `chunk_size=500` 字符
- 默认 `chunk_overlap=50` 字符
- 支持按标题、段落、固定大小三种模式
- 自动识别品牌和车型名称作为元数据标签

## 搜索流程

1. 用户查询 → 向量化
2. pgvector 余弦相似度搜索（`<=>` 操作符）
3. 返回 top_k 结果
4. 构建 LLM 上下文文本
5. 注入到 Agent 对话中

## 扩展指南

添加新的文档类型：
1. 在 `chunking.py` 添加新的切片策略
2. 在 `rag_service.py` 添加对应的 `ingest_xxx()` 方法
3. 在 `rag.py` API 添加对应端点
