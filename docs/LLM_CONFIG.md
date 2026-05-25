# LLM 配置指南

## 📋 当前配置

### 主要模型 (Primary)
- **模型**: DeepSeek V4 (`deepseek-chat`)
- **API Base URL**: `https://api.deepseek.com/v1`
- **API Key**: 从系统环境变量 `API_KEY` 读取
- **用途**: 主要对话、复杂任务处理

### 辅助模型 (Assistant)
- **模型**: Ollama Qwen3.5 9B (`qwen2.5:9b`)
- **Base URL**: `http://localhost:11434`
- **用途**: 本地快速响应、简单任务、离线备用

---

## 🔧 配置步骤

### 1. 设置系统环境变量 API_KEY

#### Windows PowerShell:
```powershell
# 临时设置 (当前会话有效)
$env:API_KEY="sk-your-deepseek-api-key"

# 永久设置
[System.Environment]::SetEnvironmentVariable('API_KEY', 'sk-your-deepseek-api-key', 'User')
```

#### Windows CMD:
```cmd
# 临时设置
set API_KEY=sk-your-deepseek-api-key

# 永久设置 (需要管理员权限)
setx API_KEY "sk-your-deepseek-api-key"
```

#### Linux/Mac:
```bash
# 编辑 ~/.bashrc 或 ~/.zshrc
export API_KEY="sk-your-deepseek-api-key"

# 生效
source ~/.bashrc
```

**验证:**
```powershell
# PowerShell
echo $env:API_KEY

# CMD
echo %API_KEY%

# Linux/Mac
echo $API_KEY
```

---

### 2. 安装并启动 Ollama

#### 下载安装 Ollama
访问: https://ollama.ai/download

#### 拉取 Qwen3.5 9B 模型
```bash
# 下载模型
ollama pull qwen3.5:9b

# 验证安装
ollama list

# 测试运行
ollama run qwen3.5:9b
```

#### 启动 Ollama 服务
```bash
# 后台运行 Ollama
ollama serve

# 默认监听端口: http://localhost:11434
```

**验证 Ollama 是否运行:**
```bash
curl http://localhost:11434/api/tags
```

---

### 3. 配置 .env 文件

```bash
# 复制示例配置
cp .env.example .env
```

编辑 `.env` 文件:

```env
# LLM 配置 - API Key (从系统环境变量读取,无需在此设置)

# 主要模型: DeepSeek V4
DEEPSEEK_API_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# 辅助模型: Ollama Qwen3.5 9B
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3.5:9b

# 默认使用的模型
DEFAULT_MODEL=deepseek-chat

# 通用配置
TEMPERATURE=0.7
MAX_TOKENS=2000

# 应用配置
APP_NAME=AutoMind AI
APP_VERSION=0.1.0
DEBUG=True

# 数据库配置
DATABASE_URL=sqlite:///./automind.db

# 爬虫配置
REQUEST_TIMEOUT=30
MAX_RETRIES=3
```

---

## 🚀 使用方式

### 默认使用 DeepSeek V4

应用启动后,默认使用 DeepSeek V4 作为主要模型:

```python
from app.services.llm_service import llm_service

# 直接使用,默认是 DeepSeek
response = llm_service.chat([
    {"role": "user", "content": "你好"}
])
```

---

### 切换到 Ollama 模型

在代码中动态切换:

```python
from app.services.llm_service import llm_service

# 切换到 Ollama 辅助模型
llm_service.set_model("assistant")

response = llm_service.chat([
    {"role": "user", "content": "你好"}
])

# 切换回 DeepSeek 主要模型
llm_service.set_model("primary")
```

---

### 在 Agent 中使用

修改 `app/agent/agent.py`,根据任务类型选择模型:

```python
def process_message(self, message: str, history: List[Dict] = None) -> str:
    """处理用户消息"""
    
    # 简单问题使用 Ollama (快速响应)
    if self._is_simple_question(message):
        llm_service.set_model("assistant")
    else:
        # 复杂问题使用 DeepSeek (更智能)
        llm_service.set_model("primary")
    
    # ... 后续处理
```

---

## 🔍 故障排查

### 问题 1: API_KEY 未找到

**错误信息:**
```
openai.AuthenticationError: The api_key client option must be set
```

**解决方案:**
```powershell
# 检查环境变量是否设置
echo $env:API_KEY

# 如果为空,重新设置
$env:API_KEY="sk-your-api-key"

# 重启应用
python run.py
```

---

### 问题 2: Ollama 连接失败

**错误信息:**
```
ConnectionRefusedError: [WinError 10061] 由于目标计算机积极拒绝，无法连接
```

**解决方案:**
```bash
# 检查 Ollama 是否运行
ollama list

# 启动 Ollama 服务
ollama serve

# 检查端口是否监听
netstat -ano | findstr :11434

# 测试连接
curl http://localhost:11434/api/tags
```

---

### 问题 3: Ollama 模型未下载

**错误信息:**
```
model "qwen3.5:9b" not found
```

**解决方案:**
```bash
# 下载模型
ollama pull qwen3.5:9b

# 查看已安装的模型
ollama list

# 如果网络慢,可以使用镜像
# 设置环境变量
$env:OLLAMA_ORIGINS="*"
```

---

### 问题 4: DeepSeek API 调用失败

**错误信息:**
```
HTTP Error 401: Unauthorized
```

**解决方案:**
1. 检查 API_KEY 是否正确
2. 确认 DeepSeek 账户余额充足
3. 验证 API Base URL 是否正确

```powershell
# 测试 DeepSeek API
curl -X POST "https://api.deepseek.com/v1/chat/completions" `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer $env:API_KEY" `
  -d '{\"model\": \"deepseek-chat\", \"messages\": [{\"role\": \"user\", \"content\": \"你好\"}]}'
```

---

## 📊 模型对比

| 特性 | DeepSeek V4 | Ollama Qwen3.5 9B |
|------|-------------|-------------------|
| **类型** | 云端 API | 本地部署 |
| **速度** | 中等 (网络依赖) | 快 (本地运行) |
| **智能程度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **成本** | 按 token 计费 | 免费 |
| **离线可用** | ❌ | ✅ |
| **隐私性** | 数据发送到云端 | 完全本地 |
| **适用场景** | 复杂推理、创意写作 | 简单问答、快速响应 |

---

## 💡 最佳实践

### 1. 混合使用策略

```python
# 根据问题复杂度选择模型
def smart_chat(message: str):
    if len(message) < 50:
        # 短问题用 Ollama
        llm_service.set_model("assistant")
    else:
        # 长问题用 DeepSeek
        llm_service.set_model("primary")
    
    return llm_service.chat([{"role": "user", "content": message}])
```

### 2. 降级策略

```python
def chat_with_fallback(message: str):
    try:
        # 优先使用 DeepSeek
        llm_service.set_model("primary")
        return llm_service.chat([{"role": "user", "content": message}])
    except Exception as e:
        logger.warning(f"DeepSeek failed: {e}, fallback to Ollama")
        # 降级到 Ollama
        llm_service.set_model("assistant")
        return llm_service.chat([{"role": "user", "content": message}])
```

### 3. 成本优化

- 简单问候、常见问题 → Ollama (免费)
- 复杂分析、专业建议 → DeepSeek (付费但更智能)

---

## 🔐 安全提示

1. **不要硬编码 API Key**: 始终使用环境变量
2. **不要提交 .env 文件**: 确保 `.gitignore` 包含 `.env`
3. **定期轮换 API Key**: 提高安全性
4. **监控 API 使用量**: 避免费用超支

---

## 📞 获取帮助

- DeepSeek 文档: https://platform.deepseek.com/docs
- Ollama 文档: https://ollama.ai/docs
- 项目 Issues: 提交问题描述

---

**最后更新**: 2026-05-18  
**配置版本**: v2.0 (DeepSeek + Ollama)
