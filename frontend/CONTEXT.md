# Frontend Context

AutoMind AI — 智能汽车价格分析助手前端界面。

## 技术栈

- **框架**: React 18
- **构建工具**: Vite 5
- **UI 库**: Ant Design 5 + @ant-design/icons
- **状态管理**: Zustand
- **HTTP 客户端**: Axios
- **路由**: React Router DOM 6
- **日期**: dayjs

## 领域语言

**会话（Session）**: 一次聊天对话，包含多条消息。侧边栏显示会话列表。

**消息（Message）**: 聊天中的一条记录，role 为 `user` 或 `assistant`。

**ChatStore**: Zustand store，管理 sessions、messages、currentSessionId、loading、error 状态。

**ChatPage**: 主聊天页面，包含侧边栏、消息列表、输入区。

**MessageList**: 渲染消息列表的组件，显示头像、内容、时间。

**Sidebar**: 侧边栏组件，显示会话列表和新建对话按钮。

## 目录结构

- `src/api/` — Axios 实例和 API 调用
- `src/stores/` — Zustand 状态管理
- `src/components/` — 可复用组件
- `src/pages/` — 页面组件
- `src/styles/` — CSS 样式

## ADR

- `frontend/docs/adr/` — 前端架构决策记录
