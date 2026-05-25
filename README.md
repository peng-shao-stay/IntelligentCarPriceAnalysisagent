# AutoMind AI — 智能汽车价格分析助手

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)
![React](https://img.shields.io/badge/React-18-blue.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

基于 AI Agent + RAG + MCP 的智能汽车价格分析系统。

支持自然语言价格查询、多车型对比、行业资讯追踪、知识库语义搜索。

</div>

---

## 功能特性

- **智能对话** — 基于 LLM Agent 的自然语言交互，自动识别意图并路由到对应工具
- **价格查询** — 实时查询各品牌汽车价格（Tavily AI 搜索 + 结构化数据库）
- **车型对比** — 多维度对比不同车型的配置、价格和性价比
- **资讯追踪** — 获取汽车行业最新新闻和分析
- **RAG 语义搜索** — 基于 pgvector 的知识库向量检索，支持上传文档自动切片
- **MCP 工具扩展** — 通过 Model Context Protocol 动态接入外部工具服务器
- **多 Agent 协作** — Searcher → Knowledge → Writer → Validator 流水线
- **管理面板** — React 管理端：用户管理、LLM 配置、RAG 管理、MCP 服务器管理

---

## 技术栈

| 层 | 技术 |
|---|------|
| 后端框架 | FastAPI + Uvicorn |
| 前端 | React 18 + Ant Design + Vite |
| AI/LLM | LangChain + DeepSeek / OpenAI / Ollama |
| 向量数据库 | PostgreSQL + pgvector |
| 缓存 | Redis |
| 搜索 | Tavily API |
| MCP | JSON-RPC 2.0 自定义实现 |
| 数据库 ORM | SQLAlchemy 2.0 |
| 认证 | JWT + bcrypt |

---

## 项目结构

```
IntelligentCarPriceAnalysisagent/
├── app/                        # 后端应用
│   ├── api/                    # FastAPI 路由
│   ├── agent/                  # 核心 Agent 循环（单 Agent 模式）
│   │   ├── tools/              # 内置工具（价格查询、对比、新闻）
│   │   └── templates/          # 回答模板
│   ├── multi_agent/            # 多 Agent 编排框架
│   │   ├── orchestrator.py     # 编排器
│   │   ├── searcher.py         # 搜索 Agent
│   │   ├── knowledge.py        # 知识库 Agent
│   │   ├── writer.py           # 写作 Agent
│   │   └── validator.py        # 验证 Agent
│   ├── mcp/                    # MCP 客户端层
│   ├── providers/              # 数据提供者抽象（Search/Vector/Database）
│   ├── services/               # 业务服务（LLM/RAG/Tavily/爬虫）
│   ├── schemas/                # Pydantic 模型
│   ├── db/                     # 数据库模型和连接
│   ├── auth/                   # JWT 认证
│   ├── core/                   # 配置和日志
│   ├── memory/                 # Redis 会话记忆
│   └── utils/                  # 工具函数
├── mcp_servers/                # MCP 服务器（独立部署）
│   ├── base.py                 # FastAPI JSON-RPC 基类
│   ├── search_server.py        # Tavily 搜索 MCP 服务
│   ├── car_data_server.py      # 数据库查询 MCP 服务
│   └── rag_server.py           # RAG 向量搜索 MCP 服务
├── frontend/                   # React 管理面板
│   └── src/
│       ├── api/                # API 调用层
│       ├── components/         # 通用组件
│       ├── pages/              # 页面（Chat/Login/Admin）
│       ├── stores/             # Zustand 状态管理
│       └── styles/             # CSS 样式
├── docs/                       # 文档
│   ├── SETUP.md                # 环境搭建指南
│   ├── ARCHITECTURE.md         # 架构说明
│   ├── API.md                  # API 文档
│   ├── AUTH.md                 # 认证说明
│   ├── LLM_CONFIG.md           # LLM 配置
│   ├── FRONTEND.md             # 前端说明
│   ├── TROUBLESHOOTING.md      # 故障排查
│   └── adr/                    # 架构决策记录
├── tests/                      # 测试
├── scripts/                    # 开发/迁移脚本
├── skills/                     # Claude Code 开发技能
├── schema.sql                  # 数据库 DDL
├── main.py                     # 应用入口
├── requirements.txt            # Python 依赖
├── pyproject.toml              # 项目配置
└── .env.example               # 环境变量模板
```

---

## 快速开始

详见 [docs/SETUP.md](docs/SETUP.md)。

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env

# 启动后端
python main.py
# → http://localhost:8000/docs

# 启动前端（可选，管理面板）
cd frontend && npm install && npm run dev
# → http://localhost:3000
```

---

## 架构概览

```
用户提问 → FastAPI → Agent Core → 意图识别
                                    ├── car_price    → Tavily 搜索 + 数据库查询
                                    ├── car_compare  → 多源对比引擎
                                    ├── news         → 新闻搜索 + 摘要
                                    └── general      → LLM 直接回复
                                           │
                                    RAG 增强:
                                    ├── pgvector 向量搜索
                                    └── LLM 上下文注入
                                           │
                                    MCP 扩展:
                                    ├── MCPClient → 外部工具服务器
                                    └── ToolDiscoveryService
```

详细架构见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

---

## API 文档

启动后端后访问 Swagger UI: http://localhost:8000/docs

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/chat/` | POST | 发送聊天消息 |
| `/api/v1/chat/sessions` | GET | 获取会话列表 |
| `/api/v1/chat/sessions/{id}` | GET | 获取会话历史 |
| `/api/v1/rag/search` | POST | RAG 语义搜索 |
| `/api/v1/rag/ingest` | POST | 录入知识库文档 |
| `/admin/mcp/servers` | GET/POST | MCP 服务器管理 |

完整 API 文档见 [docs/API.md](docs/API.md)。

---

## 测试

```bash
pytest tests/ -v
```

---

## 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/xxx`)
3. 提交更改
4. 推送到分支
5. 开启 Pull Request

---

## 许可证

MIT License — 详见 [LICENSE](LICENSE)

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给个 Star！**

</div>
