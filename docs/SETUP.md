# AutoMind AI — 完整环境搭建指南

## 前置要求

- **Python** 3.10+
- **PostgreSQL** 14+ (生产) 或 SQLite (开发)
- **Redis** 7.0+ (可选，缓存层)
- **Node.js** 16+ (前端)
- **Ollama** (可选，本地模型)

---

## 1. 快速开始（5 分钟，SQLite 模式）

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env

# 启动后端
python main.py
# → http://localhost:8000
# → API 文档: http://localhost:8000/docs

# 启动前端（新终端）
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

---

## 2. 数据库配置

### SQLite（开发/测试）

`.env` 中设置：
```env
DATABASE_URL=sqlite:///./automind.db
```

### PostgreSQL（生产）

```bash
# 安装 PostgreSQL
# Windows: https://www.postgresql.org/download/windows/
# macOS: brew install postgresql
# Linux: sudo apt install postgresql

# 创建数据库和用户
psql -U postgres
CREATE USER automind WITH PASSWORD 'your_password';
CREATE DATABASE automind_db OWNER automind;
GRANT ALL PRIVILEGES ON DATABASE automind_db TO automind;
\q

# 安装 pgvector 扩展
psql -U automind -d automind_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

`.env` 配置：
```env
DATABASE_URL=postgresql://automind:your_password@localhost:5432/automind_db
```

初始化表结构：
```bash
psql -U automind -d automind_db -f schema.sql
```

---

## 3. Redis 缓存（可选）

```bash
# Docker 方式（推荐）
docker run -d --name redis -p 6379:6379 redis:latest

# Linux
sudo apt install redis-server && sudo systemctl start redis-server

# macOS
brew install redis && brew services start redis
```

`.env` 配置：
```env
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_TTL=3600
```

---

## 4. LLM 配置

### DeepSeek（主模型）

```env
DEEPSEEK_API_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

设置 API Key：
```powershell
# Windows PowerShell（永久）
[System.Environment]::SetEnvironmentVariable('API_KEY', 'sk-your-key', 'User')

# Linux/macOS
export API_KEY="sk-your-key"
```

### Ollama 本地模型（辅助）

```bash
# 安装 Ollama: https://ollama.ai/download
ollama pull qwen3.5:9b

# 验证
curl http://localhost:11434/api/tags
```

`.env` 配置：
```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3.5:9b
DEFAULT_MODEL=deepseek-chat
```

---

## 5. Tavily AI 搜索

注册获取 API Key: https://app.tavily.com/

```env
TAVILY_API_KEY=tvly-your-key-here
```

免费额度：每月 1000 次搜索。

---

## 6. 验证安装

```bash
# 后端健康检查
curl http://localhost:8000/

# 测试聊天 API
curl -X POST "http://localhost:8000/api/v1/chat/" \
  -H "Content-Type: application/json" \
  -d '{"message": "特斯拉 Model 3 多少钱?", "session_id": null}'

# 运行测试
pytest tests/ -v
```

---

## 常见问题

| 问题 | 解决 |
|------|------|
| 端口被占用 | `netstat -ano \| findstr :8000` → `taskkill /PID <ID> /F` |
| 缺少依赖 | `pip install -r requirements.txt --force-reinstall` |
| API Key 未配置 | Windows: `echo $env:API_KEY`，Linux: `echo $API_KEY` |
| 数据库连接失败 | 检查 PostgreSQL 服务是否运行，`.env` 中密码是否正确 |
| Redis 连接失败 | `redis-cli ping`，确认服务运行中 |

更多故障排查见 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)。
