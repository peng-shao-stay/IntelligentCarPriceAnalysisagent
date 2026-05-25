# 常见问题与解决方案

## ❌ 错误: ModuleNotFoundError: No module named 'langchain.schema'

### 问题原因
LangChain 在新版本中重构了模块结构,`langchain.schema` 已被移除,消息类型移到了 `langchain_core.messages`。

### ✅ 解决方案

#### 方法 1: 重新安装依赖 (推荐)

```powershell
# 进入项目目录
cd D:\PythonProject\peng-shao-stay-IntelligentCarPriceAnalysisagent

# 重新安装所有依赖
pip install -r requirements.txt --force-reinstall

# 或使用 uv (更快)
uv pip sync requirements.txt
```

---

#### 方法 2: 单独安装 langchain-core

```powershell
pip install langchain-core>=0.1.0
```

---

### 🔍 验证修复

```powershell
# 测试导入
python -c "from langchain_core.messages import HumanMessage, AIMessage, SystemMessage; print('✅ 导入成功')"

# 启动应用
python run.py
```

---

## ❌ 错误: ImportError: cannot import name 'ChatOllama'

### 问题原因
`langchain-community` 未安装或版本过低。

### ✅ 解决方案

```powershell
# 安装或更新 langchain-community
pip install langchain-community>=0.0.10 --force-reinstall
```

---

## ❌ 错误: ConnectionRefusedError - Ollama 连接失败

### 问题原因
Ollama 服务未启动。

### ✅ 解决方案

```powershell
# 检查 Ollama 是否运行
ollama list

# 启动 Ollama 服务
ollama serve

# 验证端口
curl http://localhost:11434/api/tags
```

---

## ❌ 错误: AuthenticationError - DeepSeek API Key 无效

### 问题原因
API_KEY 环境变量未设置或值不正确。

### ✅ 解决方案

```powershell
# 检查环境变量
echo $env:API_KEY

# 如果为空,设置 API Key
$env:API_KEY="sk-your-deepseek-api-key"

# 永久设置
[System.Environment]::SetEnvironmentVariable('API_KEY', 'sk-your-key', 'User')

# 重启终端后生效
```

---

## ❌ 错误: Port 8000 already in use

### 问题原因
端口 8000 被其他进程占用。

### ✅ 解决方案

```powershell
# 查找占用端口的进程
netstat -ano | findstr :8000

# 假设 PID 是 12345,终止进程
taskkill /PID 12345 /F

# 或使用其他端口
python -c "import uvicorn; uvicorn.run('main:app', port=8001)"
```

---

## ❌ 错误: Database error - unable to open database file

### 问题原因
数据库文件权限问题或路径错误。

### ✅ 解决方案

```powershell
# 删除旧数据库
rm automind.db

# 重启应用会自动创建
python run.py
```

---

## ❌ 错误: Python version mismatch

### 问题原因
Python 版本低于 3.10。

### ✅ 解决方案

```powershell
# 检查 Python 版本
python --version

# 需要 Python 3.10+
# 如果版本过低,请升级到 Python 3.10 或更高版本
```

---

## 🔧 通用故障排查步骤

### 1. 运行配置检查脚本

```powershell
python check_llm_config.py
```

这会检查:
- API_KEY 环境变量
- Ollama 服务状态
- Python 依赖
- 配置文件

---

### 2. 清理并重新安装

```powershell
# 删除虚拟环境 (如果使用)
rm -r .venv

# 重新创建
python -m venv .venv

# 激活
.venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt
```

---

### 3. 检查日志文件

```powershell
# 查看应用日志
cat logs/app_*.log

# 查看错误日志
cat logs/error_*.log
```

---

### 4. 测试单个组件

```powershell
# 测试 FastAPI 导入
python -c "from fastapi import FastAPI; print('✅ FastAPI OK')"

# 测试 LangChain 导入
python -c "from langchain_core.messages import HumanMessage; print('✅ LangChain OK')"

# 测试数据库
python -c "from app.db.database import engine; print('✅ Database OK')"

# 测试配置
python -c "from app.core.config import settings; print('✅ Config OK')"
```

---

## 📞 仍然有问题?

1. **查看详细文档**:
   - [LLM 配置指南](LLM_CONFIG.md)
   - [快速配置指南](SETUP_GUIDE.md)

2. **检查 GitHub Issues**:
   - 搜索类似问题
   - 提交新问题

3. **提供以下信息**:
   - 完整的错误堆栈
   - Python 版本: `python --version`
   - 依赖版本: `pip list`
   - 操作系统版本

---

**最后更新**: 2026-05-18
