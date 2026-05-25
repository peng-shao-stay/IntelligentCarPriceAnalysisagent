# AutoMind AI API 使用示例

## 📡 API 基础信息

- **Base URL**: `http://localhost:8000`
- **API 版本**: v1
- **API 前缀**: `/api/v1`
- **文档地址**: http://localhost:8000/docs

## 🔑 认证

当前版本暂不需要认证,生产环境建议添加 API Key 或 JWT。

---

## 💬 聊天接口

### 1. 发送消息

**端点**: `POST /api/v1/chat/`

**请求体**:
```json
{
  "message": "特斯拉 Model 3 多少钱?",
  "session_id": null
}
```

**参数说明**:
- `message` (string, required): 用户消息内容
- `session_id` (string, optional): 会话ID,不传则创建新会话

**响应示例**:
```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "user_message": {
    "id": 1,
    "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "role": "user",
    "content": "特斯拉 Model 3 多少钱?",
    "timestamp": "2026-05-18T10:30:00"
  },
  "assistant_message": {
    "id": 2,
    "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "role": "assistant",
    "content": "特斯拉 Model 3 的官方指导价如下:\n\n- 后轮驱动版: ¥231,900\n- 长续航全轮驱动版: ¥271,900\n- Performance高性能版: ¥331,900\n\n以上价格为官方指导价,实际成交价可能因地区和优惠政策有所不同。",
    "timestamp": "2026-05-18T10:30:05"
  }
}
```

**cURL 示例**:
```bash
curl -X POST "http://localhost:8000/api/v1/chat/" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "特斯拉 Model 3 多少钱?",
    "session_id": null
  }'
```

**Python 示例**:
```python
import requests

url = "http://localhost:8000/api/v1/chat/"
payload = {
    "message": "特斯拉 Model 3 多少钱?",
    "session_id": None
}

response = requests.post(url, json=payload)
print(response.json())
```

**JavaScript 示例**:
```javascript
fetch('http://localhost:8000/api/v1/chat/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    message: '特斯拉 Model 3 多少钱?',
    session_id: null
  })
})
.then(response => response.json())
.then(data => console.log(data));
```

---

### 2. 获取会话列表

**端点**: `GET /api/v1/chat/sessions`

**查询参数**: 无

**响应示例**:
```json
[
  {
    "id": 1,
    "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "title": "特斯拉 Model 3 多少钱?",
    "created_at": "2026-05-18T10:30:00",
    "updated_at": "2026-05-18T10:35:00"
  },
  {
    "id": 2,
    "session_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "title": "对比比亚迪汉和特斯拉",
    "created_at": "2026-05-18T09:20:00",
    "updated_at": "2026-05-18T09:25:00"
  }
]
```

**cURL 示例**:
```bash
curl -X GET "http://localhost:8000/api/v1/chat/sessions"
```

**Python 示例**:
```python
import requests

url = "http://localhost:8000/api/v1/chat/sessions"
response = requests.get(url)
sessions = response.json()

for session in sessions:
    print(f"{session['title']} - {session['session_id']}")
```

---

### 3. 获取会话历史

**端点**: `GET /api/v1/chat/sessions/{session_id}`

**路径参数**:
- `session_id` (string): 会话ID

**响应示例**:
```json
{
  "session": {
    "id": 1,
    "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "title": "特斯拉 Model 3 多少钱?",
    "created_at": "2026-05-18T10:30:00",
    "updated_at": "2026-05-18T10:35:00"
  },
  "messages": [
    {
      "id": 1,
      "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "role": "user",
      "content": "特斯拉 Model 3 多少钱?",
      "timestamp": "2026-05-18T10:30:00"
    },
    {
      "id": 2,
      "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "role": "assistant",
      "content": "特斯拉 Model 3 的官方指导价如下...",
      "timestamp": "2026-05-18T10:30:05"
    },
    {
      "id": 3,
      "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "role": "user",
      "content": "有优惠吗?",
      "timestamp": "2026-05-18T10:31:00"
    },
    {
      "id": 4,
      "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "role": "assistant",
      "content": "目前部分地区有...",
      "timestamp": "2026-05-18T10:31:05"
    }
  ]
}
```

**cURL 示例**:
```bash
curl -X GET "http://localhost:8000/api/v1/chat/sessions/a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

**Python 示例**:
```python
import requests

session_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
url = f"http://localhost:8000/api/v1/chat/sessions/{session_id}"

response = requests.get(url)
data = response.json()

print(f"会话标题: {data['session']['title']}")
print(f"消息数量: {len(data['messages'])}")

for msg in data['messages']:
    role = "👤 用户" if msg['role'] == 'user' else "🤖 AI"
    print(f"\n{role}:")
    print(msg['content'])
```

---

### 4. 删除会话

**端点**: `DELETE /api/v1/chat/sessions/{session_id}`

**路径参数**:
- `session_id` (string): 会话ID

**响应示例**:
```json
{
  "message": "会话已删除"
}
```

**cURL 示例**:
```bash
curl -X DELETE "http://localhost:8000/api/v1/chat/sessions/a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

**Python 示例**:
```python
import requests

session_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
url = f"http://localhost:8000/api/v1/chat/sessions/{session_id}"

response = requests.delete(url)
print(response.json())
```

---

## 🔍 其他接口

### 健康检查

**端点**: `GET /health`

**响应示例**:
```json
{
  "status": "healthy"
}
```

**cURL 示例**:
```bash
curl -X GET "http://localhost:8000/health"
```

---

### 根路径

**端点**: `GET /`

**响应示例**:
```json
{
  "message": "Welcome to AutoMind AI",
  "version": "0.1.0",
  "docs": "/docs"
}
```

---

## 💡 完整使用流程示例

### Python 完整示例

```python
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

class AutoMindClient:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.session_id = None
    
    def chat(self, message: str) -> dict:
        """发送消息并获取回复"""
        url = f"{self.base_url}/chat/"
        payload = {
            "message": message,
            "session_id": self.session_id
        }
        
        response = requests.post(url, json=payload)
        data = response.json()
        
        # 保存 session_id 用于后续对话
        self.session_id = data['session_id']
        
        return data
    
    def get_history(self) -> dict:
        """获取当前会话历史"""
        if not self.session_id:
            raise Exception("没有活跃的会话")
        
        url = f"{self.base_url}/chat/sessions/{self.session_id}"
        response = requests.get(url)
        return response.json()
    
    def list_sessions(self) -> list:
        """获取所有会话列表"""
        url = f"{self.base_url}/chat/sessions"
        response = requests.get(url)
        return response.json()
    
    def delete_session(self, session_id: str = None) -> dict:
        """删除指定会话"""
        sid = session_id or self.session_id
        if not sid:
            raise Exception("没有指定会话ID")
        
        url = f"{self.base_url}/chat/sessions/{sid}"
        response = requests.delete(url)
        
        if session_id == self.session_id:
            self.session_id = None
        
        return response.json()


# 使用示例
if __name__ == "__main__":
    client = AutoMindClient()
    
    # 第一次对话
    print("🤖 询问特斯拉价格...")
    response = client.chat("特斯拉 Model 3 多少钱?")
    print(f"AI: {response['assistant_message']['content']}\n")
    
    # 继续对话
    print("🤖 询问优惠信息...")
    response = client.chat("现在有优惠吗?")
    print(f"AI: {response['assistant_message']['content']}\n")
    
    # 查看历史
    print("📜 查看对话历史...")
    history = client.get_history()
    print(f"会话标题: {history['session']['title']}")
    print(f"消息数量: {len(history['messages'])}\n")
    
    # 列出所有会话
    print("📋 所有会话:")
    sessions = client.list_sessions()
    for i, session in enumerate(sessions, 1):
        print(f"{i}. {session['title']}")
```

### JavaScript 完整示例

```javascript
class AutoMindClient {
  constructor(baseUrl = 'http://localhost:8000/api/v1') {
    this.baseUrl = baseUrl;
    this.sessionId = null;
  }

  async chat(message) {
    const url = `${this.baseUrl}/chat/`;
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: message,
        session_id: this.sessionId
      })
    });
    
    const data = await response.json();
    this.sessionId = data.session_id;
    return data;
  }

  async getHistory() {
    if (!this.sessionId) {
      throw new Error('没有活跃的会话');
    }
    
    const url = `${this.baseUrl}/chat/sessions/${this.sessionId}`;
    const response = await fetch(url);
    return await response.json();
  }

  async listSessions() {
    const url = `${this.baseUrl}/chat/sessions`;
    const response = await fetch(url);
    return await response.json();
  }

  async deleteSession(sessionId = null) {
    const sid = sessionId || this.sessionId;
    if (!sid) {
      throw new Error('没有指定会话ID');
    }
    
    const url = `${this.baseUrl}/chat/sessions/${sid}`;
    const response = await fetch(url, { method: 'DELETE' });
    
    if (sessionId === this.sessionId) {
      this.sessionId = null;
    }
    
    return await response.json();
  }
}

// 使用示例
(async () => {
  const client = new AutoMindClient();
  
  // 发送消息
  console.log('🤖 询问特斯拉价格...');
  const response = await client.chat('特斯拉 Model 3 多少钱?');
  console.log('AI:', response.assistant_message.content);
  
  // 继续对话
  console.log('\n🤖 询问优惠信息...');
  const response2 = await client.chat('现在有优惠吗?');
  console.log('AI:', response2.assistant_message.content);
  
  // 查看历史
  console.log('\n📜 查看对话历史...');
  const history = await client.getHistory();
  console.log('会话标题:', history.session.title);
  console.log('消息数量:', history.messages.length);
})();
```

---

## ⚠️ 错误处理

### 常见错误响应

**404 - 会话不存在**:
```json
{
  "detail": "会话不存在"
}
```

**500 - 服务器错误**:
```json
{
  "detail": "具体错误信息"
}
```

**422 - 验证错误**:
```json
{
  "detail": [
    {
      "loc": ["body", "message"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 错误处理示例 (Python)

```python
import requests
from requests.exceptions import HTTPError

try:
    response = requests.post(
        "http://localhost:8000/api/v1/chat/",
        json={"message": "", "session_id": None}  # 空消息会触发验证错误
    )
    response.raise_for_status()
    data = response.json()
except HTTPError as e:
    if e.response.status_code == 422:
        print("验证错误:", e.response.json()['detail'])
    elif e.response.status_code == 404:
        print("会话不存在")
    elif e.response.status_code == 500:
        print("服务器错误:", e.response.json()['detail'])
    else:
        print(f"HTTP 错误: {e}")
except Exception as e:
    print(f"请求失败: {e}")
```

---

## 📊 性能建议

1. **批量操作**: 避免频繁创建新会话,复用 session_id
2. **缓存**: 对常用查询结果进行客户端缓存
3. **超时设置**: 设置合理的请求超时时间
4. **重试机制**: 对失败请求实现指数退避重试
5. **连接池**: 使用连接池提高性能

---

## 🔐 安全建议 (生产环境)

1. **添加认证**: 使用 API Key 或 JWT
2. **HTTPS**: 启用 SSL/TLS
3. **速率限制**: 防止 API 滥用
4. **输入验证**: 服务端严格验证所有输入
5. **CORS 配置**: 限制允许的域名
6. **错误信息**: 不要暴露敏感信息

---

**最后更新**: 2026-05-18  
**API 版本**: v1
