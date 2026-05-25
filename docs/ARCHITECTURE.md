# AutoMind AI 项目架构说明

## 📊 架构图

```
┌─────────────────────────────────────────────────┐
│                  Client (前端/Postman)            │
└────────────────┬────────────────────────────────┘
                 │ HTTP Requests
                 ▼
┌─────────────────────────────────────────────────┐
│              FastAPI Application                  │
│  ┌───────────────────────────────────────────┐  │
│  │         API Routes (app/api/)              │  │
│  │  - POST /api/v1/chat/                      │  │
│  │  - GET  /api/v1/chat/sessions              │  │
│  │  - GET  /api/v1/chat/sessions/{id}         │  │
│  │  - DELETE /api/v1/chat/sessions/{id}       │  │
│  └───────────────┬───────────────────────────┘  │
│                  │                               │
│  ┌───────────────▼───────────────────────────┐  │
│  │      Agent Core (app/agent/)               │  │
│  │  ┌────────────┐  ┌──────────────────┐    │  │
│  │  │ Intent     │→ │ Tool Selection   │    │  │
│  │  │ Detection  │  │ & Execution      │    │  │
│  │  └────────────┘  └────────┬─────────┘    │  │
│  │                           │               │  │
│  │  ┌────────────────────────▼──────────┐   │  │
│  │  │        Tools (app/agent/tools/)   │   │  │
│  │  │  - car_price.py                   │   │  │
│  │  │  - news_search.py                 │   │  │
│  │  │  - compare.py                     │   │  │
│  │  └────────────────────────┬──────────┘   │  │
│  └───────────────────────────┼──────────────┘  │
│                              │                  │
│  ┌───────────────────────────▼──────────────┐  │
│  │      Services Layer (app/services/)      │  │
│  │  ┌──────────────┐  ┌────────────────┐  │  │
│  │  │ LLM Service  │  │ Crawler        │  │  │
│  │  │              │  │ Service        │  │  │
│  │  └──────────────┘  └────────────────┘  │  │
│  └──────────────────────────┬─────────────┘  │
│                             │                 │
│  ┌──────────────────────────▼─────────────┐  │
│  │      Database (app/db/)                │  │
│  │  - Chat Sessions                       │  │
│  │  - Chat Messages                       │  │
│  │  - Car Prices                          │  │
│  │  - News Articles                       │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

## 🏗️ 分层架构说明

### 1. **API 层 (app/api/)**
- **职责**: 处理 HTTP 请求和响应
- **主要文件**:
  - `chat.py`: 聊天相关的所有接口
  
**特点**:
- 使用 Pydantic 模型进行请求/响应验证
- 依赖注入数据库会话
- 统一的错误处理

### 2. **Agent 层 (app/agent/)**
- **职责**: 核心业务逻辑,意图识别和工具调度
- **主要组件**:
  - `agent.py`: Agent 主控制器
  - `prompts.py`: LLM 提示词模板
  - `tools/`: 各种工具函数

**工作流程**:
```
用户消息 → 意图识别 → 选择工具 → 执行工具 → 返回结果
```

### 3. **服务层 (app/services/)**
- **职责**: 封装外部服务和复杂业务逻辑
- **主要服务**:
  - `llm_service.py`: LLM 调用封装
  - `crawler_service.py`: 爬虫服务封装

**优势**:
- 解耦具体实现
- 便于替换和扩展
- 统一错误处理

### 4. **数据层 (app/db/)**
- **职责**: 数据持久化
- **主要组件**:
  - `database.py`: 数据库连接管理
  - `models.py`: SQLAlchemy 数据模型

**特性**:
- ORM 抽象
- 会话管理
- 自动建表

### 5. **Schema 层 (app/schemas/)**
- **职责**: 数据验证和序列化
- **使用**: Pydantic 模型
- **用途**:
  - API 请求验证
  - 响应格式化
  - 类型安全

### 6. **核心配置 (app/core/)**
- **职责**: 全局配置和日志
- **主要文件**:
  - `config.py`: 环境变量管理
  - `logging.py`: 日志系统配置

### 7. **工具层 (app/utils/)**
- **职责**: 通用辅助函数
- **示例功能**:
  - 文本处理
  - 日期解析
  - URL 验证

## 🔄 数据流示例

### 场景: 用户询问汽车价格

```
1. 用户发送: "特斯拉 Model 3 多少钱?"
   ↓
2. API 层接收: POST /api/v1/chat/
   ↓
3. 保存到数据库: ChatMessage (user)
   ↓
4. Agent 处理:
   - 意图识别: "car_price"
   - 调用工具: query_car_price()
   ↓
5. 服务层执行:
   - CrawlerService 获取价格数据
   ↓
6. Agent 生成回复:
   - LLM Service 生成自然语言回答
   ↓
7. 保存到数据库: ChatMessage (assistant)
   ↓
8. 返回响应给客户端
```

## 📦 模块依赖关系

```
main.py
  ├── app.api.chat
  │   ├── app.agent.agent
  │   │   ├── app.services.llm_service
  │   │   ├── app.services.crawler_service
  │   │   └── app.agent.tools.*
  │   ├── app.db.models
  │   └── app.schemas.chat
  ├── app.core.config
  └── app.core.logging
```

## 🎯 设计原则

### 1. **单一职责**
每个模块只负责一个功能领域

### 2. **依赖倒置**
高层模块不依赖低层模块的具体实现

### 3. **开闭原则**
对扩展开放,对修改关闭

### 4. **接口隔离**
使用清晰的接口定义模块间交互

## 🔧 扩展指南

### 添加新功能模块

1. **创建 Schema** (`app/schemas/new_feature.py`)
2. **创建数据模型** (`app/db/models.py`)
3. **实现服务** (`app/services/new_service.py`)
4. **添加工具** (`app/agent/tools/new_tool.py`)
5. **更新 Agent** (`app/agent/agent.py`)
6. **创建 API** (`app/api/new_api.py`)
7. **注册路由** (`main.py`)

### 示例: 添加"价格预警"功能

```python
# 1. Schema
class PriceAlertCreate(BaseModel):
    brand: str
    model: str
    target_price: float

# 2. Model
class PriceAlert(Base):
    __tablename__ = "price_alerts"
    # ...

# 3. Service
class AlertService:
    def check_prices(self):
        # 检查价格是否达到目标

# 4. Tool
def create_price_alert(brand, model, target_price):
    # 创建预警

# 5. Agent
def _handle_price_alert(self, message):
    # 处理预警请求

# 6. API
@router.post("/alerts")
def create_alert(...):
    # API 端点
```

## 🚀 性能优化建议

1. **缓存**: 添加 Redis 缓存热门查询
2. **异步**: 使用 FastAPI 的异步特性
3. **批量操作**: 批量保存消息到数据库
4. **连接池**: 配置数据库连接池
5. **限流**: 添加 API 速率限制

## 🔒 安全考虑

1. **API Key 保护**: 使用环境变量
2. **输入验证**: Pydantic 模型验证
3. **SQL 注入防护**: 使用 ORM
4. **CORS 配置**: 限制允许的源
5. **错误处理**: 不暴露敏感信息

## 📝 最佳实践

1. **日志记录**: 关键操作都要记录日志
2. **异常处理**: 统一的异常处理机制
3. **文档**: 保持 API 文档更新
4. **测试**: 编写单元测试和集成测试
5. **代码审查**: 提交前进行代码审查

---

**最后更新**: 2026-05-18
