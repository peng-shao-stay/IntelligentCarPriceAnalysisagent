# AutoMind AI Frontend

智能汽车价格分析助手 - React 前端

## 技术栈

- **React 18** - UI 框架
- **Vite** - 构建工具
- **Ant Design** - UI 组件库
- **Zustand** - 状态管理
- **Axios** - HTTP 客户端
- **React Router** - 路由管理

## 快速开始

### 1. 安装依赖

```bash
cd frontend
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:3000

### 3. 构建生产版本

```bash
npm run build
```

## 项目结构

```
frontend/
├── src/
│   ├── api/              # API 接口层
│   │   ├── index.js      # Axios 配置
│   │   └── chat.js       # 聊天相关 API
│   ├── components/       # 通用组件
│   │   ├── Sidebar.jsx   # 侧边栏（会话列表）
│   │   └── MessageList.jsx  # 消息列表
│   ├── pages/            # 页面组件
│   │   └── ChatPage.jsx  # 聊天页面
│   ├── stores/           # 状态管理
│   │   └── useChatStore.js  # 聊天状态
│   ├── styles/           # 样式文件
│   │   ├── ChatPage.css
│   │   ├── Sidebar.css
│   │   └── MessageList.css
│   ├── App.jsx           # 主应用组件
│   ├── main.jsx          # 入口文件
│   └── index.css         # 全局样式
├── index.html
├── package.json
├── vite.config.js        # Vite 配置
└── .gitignore
```

## 功能特性

✅ 实时聊天界面
✅ 会话管理（创建、切换、查看）
✅ 消息历史记录
✅ 响应式设计
✅ 加载状态提示
✅ 错误处理

## API 代理配置

开发环境下，Vite 会自动代理 API 请求到后端：

- 前端: http://localhost:3000
- 后端: http://localhost:8000

所有 `/api` 开头的请求会被代理到后端服务器。

## 注意事项

1. **先启动后端**: 确保后端服务运行在 http://localhost:8000
2. **CORS 配置**: 后端已配置允许跨域请求
3. **数据库**: 确保 PostgreSQL 正常运行且表已创建

## 开发建议

- 使用 Chrome DevTools 调试
- 查看 Network 面板监控 API 请求
- 使用 React Developer Tools 扩展

## 下一步优化

- [ ] 添加 Markdown 渲染支持
- [ ] 实现消息搜索功能
- [ ] 添加导出聊天记录功能
- [ ] 优化移动端体验
- [ ] 添加主题切换
- [ ] 实现 WebSocket 实时通信
