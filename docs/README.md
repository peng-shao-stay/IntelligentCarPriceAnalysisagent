# docs/ — 项目文档目录规范

## 目录结构

```
docs/
├── README.md              # 本文件 — 文档导航
├── SETUP.md               # 完整环境搭建指南（安装、配置、LLM、Tavily、Redis）
├── ARCHITECTURE.md        # 系统架构说明（分层、数据流、Agent 模式）
├── API.md                 # API 接口文档（端点、请求/响应示例）
├── AUTH.md                # 认证说明（JWT、权限模型）
├── LLM_CONFIG.md          # LLM 配置指南（DeepSeek、Ollama、模型切换）
├── FRONTEND.md            # 前端开发指南（React、Vite、组件说明）
├── TROUBLESHOOTING.md     # 常见问题排查
├── CONTEXT.md             # 项目领域上下文（供 AI Agent 使用）
├── adr/                   # 架构决策记录（Architecture Decision Records）
│   └── 0001-*.md          # ADR 格式：序号-简短描述
└── agents/                # Agent 设计文档
    ├── domain.md          # 领域模型定义
    ├── issue-tracker.md   # Issue 追踪规范
    └── triage-labels.md   # Triage 标签规范
```

## 文档编写规范

1. **每个文档只负责一个主题**
2. **文件名使用大写英文**（如 `SETUP.md`、`ARCHITECTURE.md`）
3. **使用 Markdown 格式**，保持层级清晰
4. **代码示例必须有语言标记**（```bash、```python、```json）
5. **不在文档中写日期**（文档应该描述当前状态，git log 负责历史）
6. **外部链接用完整 URL**，内部链接用相对路径

## 文档更新原则

- 功能变更 → 更新对应文档
- 新功能 → 新增文档并更新本 README
- 删除功能 → 同步删除或归档相关文档
