# Backend Context

AutoMind AI — 智能汽车价格分析助手后端服务。

## 技术栈

- **语言**: Python 3.12+
- **框架**: FastAPI
- **数据库**: PostgreSQL + pgvector（向量搜索）
- **缓存**: Redis
- **LLM**: DeepSeek + Ollama（通过 LangChain）
- **搜索**: Tavily AI Search
- **爬虫**: BeautifulSoup4 + lxml

## 领域语言

**智能体（Agent）**: `AutoMindAgent`，核心分析引擎，根据用户意图匹配工具并执行。

**意图（Intent）**: 用户消息的分类 — `car_price`（查价格）、`car_compare`（对比车型）、`news`（新闻）、`general`（通用对话）。

**工具（Tool）**: Agent 可调用的能力单元，注册在 `ToolRegistry` 中。

**车型信息（CarInfo）**: 从用户消息中提取的 `{brand, model, version}` 三元组。

**价格快照（CarPriceSnapshot）**: 某品牌车型在某个时间点的价格记录。

## 目录结构

- `app/agent/` — AutoMindAgent 核心
- `app/api/` — FastAPI 路由
- `app/db/` — 数据库模型和连接
- `app/services/` — 外部服务（LLM, Tavily, 爬虫）
- `app/core/` — 配置、日志
- `app/schemas/` — Pydantic 数据模型
- `app/utils/` — 工具函数

## ADR

- `app/docs/adr/` — 后端架构决策记录
