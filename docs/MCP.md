# mcp/ — MCP 客户端层规范

> MCP (Model Context Protocol) 允许 Agent 动态发现和调用外部工具服务器。

## 模块结构

```
app/mcp/                    # MCP 客户端（Agent 侧）
├── models.py               # 数据模型（JSONRPC、MCPServerConfig、MCPTool）
├── client.py               # MCPClient — JSON-RPC 2.0 HTTP 客户端
├── adapter.py              # MCPConfigService + Provider 适配器
└── __init__.py

mcp_servers/                # MCP 服务器（工具侧，独立部署）
├── base.py                 # BaseMCPServer — FastAPI JSON-RPC 基类
├── search_server.py        # Tavily 搜索服务（端口 9100）
├── car_data_server.py      # 数据库查询服务（端口 9101）
├── rag_server.py           # RAG 向量搜索服务（端口 9102）
└── run_all.py              # 一键启动所有服务器

app/agent/discovery.py      # ToolDiscoveryService — 工具发现与注册
app/api/mcp.py              # MCP 管理 API（CRUD、测试连接、发现工具）
app/schemas/mcp.py          # Pydantic 请求/响应模型
```

## 架构流程

```
┌─────────────────────────────────────────┐
│              Agent 侧                     │
│                                          │
│  ToolDiscoveryService                    │
│    ↓ 加载配置                              │
│  MCPServerConfig (from DB)               │
│    ↓ 创建客户端                            │
│  MCPClient ──── HTTP POST / ────→  MCP Server (独立进程)
│    ↓ JSON-RPC 2.0                    ↓
│  tools/list → MCPTool[]             handle_list_tools()
│  tools/call → MCPToolCallResult     handle_call_tool()
│    ↓                                   ↓
│  AgentTool (注册到 ToolRegistry)      具体工具实现
└─────────────────────────────────────────┘
```

## 通信协议

- **传输**: HTTP POST，单端点 `/`
- **协议**: JSON-RPC 2.0
- **认证**: Bearer Token 或 API Key (通过 HTTP Header)
- **方法**:
  - `tools/list` — 获取工具列表 + JSON Schema
  - `tools/call` — 调用工具，传入 `name` + `arguments`

## 添加新的 MCP 服务器

1. 继承 `mcp_servers.base.BaseMCPServer`
2. 使用 `register_tool(MCPToolDef(...))` 注册工具
3. 定义 `input_schema` (JSON Schema 格式)
4. 实现 handler 函数
5. 在 `run_all.py` 中添加启动选项

## 数据库配置

MCP 服务器配置存储在 `app.mcp_server_configs` 表：

| 字段 | 说明 |
|------|------|
| name | 唯一服务器名称 |
| transport | http / stdio / sse |
| base_url | HTTP 端点 URL |
| auth_type | none / bearer / api_key |
| is_enabled | 是否启用 |
| is_essential | 是否必需（不可从管理面板禁用/删除） |
| tool_schemas | 缓存的工具列表 JSON |
