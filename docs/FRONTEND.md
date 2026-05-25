# AutoMind AI 前端开发指南

## 技术栈选择

本项目提供两种前端方案，请选择其中一种：

### 方案 A: React + Vite（推荐）
- **框架**: React 18
- **构建工具**: Vite
- **UI 库**: Ant Design / Material-UI
- **状态管理**: Zustand / Redux Toolkit
- **HTTP 客户端**: Axios
- **路由**: React Router v6

### 方案 B: Vue 3 + Vite
- **框架**: Vue 3 (Composition API)
- **构建工具**: Vite
- **UI 库**: Element Plus / Ant Design Vue
- **状态管理**: Pinia
- **HTTP 客户端**: Axios
- **路由**: Vue Router 4

---

## 快速开始 - React 版本

### 1. 创建 React 项目

```bash
cd D:\PythonProject\peng-shao-stay-IntelligentCarPriceAnalysisagent
npm create vite@latest frontend -- --template react
cd frontend
npm install
```

### 2. 安装依赖

```bash
# UI 组件库
npm install antd @ant-design/icons

# HTTP 客户端
npm install axios

# 路由
npm install react-router-dom

# 状态管理
npm install zustand

# 工具库
npm install dayjs lodash-es
```

### 3. 项目结构

```
frontend/
├── public/
├── src/
│   ├── api/              # API 接口
│   │   ├── index.js
│   │   └── chat.js
│   ├── components/       # 通用组件
│   │   ├── ChatWindow.jsx
│   │   ├── MessageList.jsx
│   │   └── Sidebar.jsx
│   ├── pages/            # 页面组件
│   │   ├── Home.jsx
│   │   └── Chat.jsx
│   ├── stores/           # 状态管理
│   │   └── useChatStore.js
│   ├── styles/           # 样式文件
│   │   └── App.css
│   ├── App.jsx
│   └── main.jsx
├── package.json
└── vite.config.js
```

### 4. 配置 Vite 代理

编辑 `vite.config.js`:

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
```

### 5. 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:3000

---

## 快速开始 - Vue 版本

### 1. 创建 Vue 项目

```bash
cd D:\PythonProject\peng-shao-stay-IntelligentCarPriceAnalysisagent
npm create vite@latest frontend -- --template vue
cd frontend
npm install
```

### 2. 安装依赖

```bash
# UI 组件库
npm install element-plus @element-plus/icons-vue

# HTTP 客户端
npm install axios

# 路由
npm install vue-router@4

# 状态管理
npm install pinia

# 工具库
npm install dayjs lodash-es
```

### 3. 项目结构

```
frontend/
├── public/
├── src/
│   ├── api/              # API 接口
│   │   ├── index.js
│   │   └── chat.js
│   ├── components/       # 通用组件
│   │   ├── ChatWindow.vue
│   │   ├── MessageList.vue
│   │   └── Sidebar.vue
│   ├── pages/            # 页面组件
│   │   ├── Home.vue
│   │   └── Chat.vue
│   ├── stores/           # 状态管理
│   │   └── chat.js
│   ├── styles/           # 样式文件
│   │   └── App.css
│   ├── App.vue
│   └── main.js
├── package.json
└── vite.config.js
```

### 4. 配置 Vite 代理

编辑 `vite.config.js`:

```javascript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
```

### 5. 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:3000

---

## API 接口说明

后端 API 基础地址: `http://localhost:8000/api/v1`

### 主要接口

1. **发送消息**
   ```
   POST /api/v1/chat
   Body: { "message": "用户消息", "session_id": "可选" }
   ```

2. **获取会话列表**
   ```
   GET /api/v1/sessions
   ```

3. **获取会话消息**
   ```
   GET /api/v1/sessions/{session_id}/messages
   ```

4. **健康检查**
   ```
   GET /health
   ```

---

## 开发建议

1. **先选择框架**: React 或 Vue（不要混用）
2. **使用组件库**: 加速开发，保持 UI 一致性
3. **配置代理**: 避免跨域问题
4. **模块化开发**: API、组件、状态管理分离
5. **响应式设计**: 适配移动端和桌面端

---

## 下一步

1. 选择 React 或 Vue
2. 按照上述步骤创建项目
3. 开发聊天界面
4. 集成后端 API
5. 测试和优化

需要我帮你创建具体的前端代码吗？请告诉我你选择哪个框架！
