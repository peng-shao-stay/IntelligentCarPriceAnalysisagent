import { create } from 'zustand'
import { message } from 'antd'
import { sendMessage, getSessions, getSessionMessages, deleteSession } from '../api/chat'

const useChatStore = create((set, get) => ({
  // 状态
  sessions: [],
  currentSessionId: null,
  messages: [],
  loading: false,
  sessionsLoading: false,
  error: null,

  // 获取会话列表
  fetchSessions: async () => {
    try {
      set({ sessionsLoading: true })
      const sessions = await getSessions()
      set({ sessions, sessionsLoading: false })
    } catch (error) {
      set({ error: error.message, sessionsLoading: false })
    }
  },

  // 选择会话
  selectSession: async (sessionId) => {
    const previousId = get().currentSessionId
    try {
      set({ loading: true, currentSessionId: sessionId })
      const response = await getSessionMessages(sessionId)
      // 后端返回的是 { session: {...}, messages: [...] }
      const messages = response.messages || []
      set({ messages, loading: false })
    } catch (error) {
      set({
        error: error.message,
        loading: false,
        currentSessionId: previousId,
      })
    }
  },

  // 联网搜索开关
  webSearchEnabled: false,
  setWebSearchEnabled: (enabled) => set({ webSearchEnabled: enabled }),

  // 发送消息
  sendUserMessage: async (message) => {
    const { currentSessionId, webSearchEnabled } = get()

    const msgId = Date.now()
    const userMessage = {
      id: msgId,
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
      status: 'sending',
      ...(webSearchEnabled && { web_search: true }),
    }

    set((state) => ({
      messages: [...state.messages, userMessage],
      loading: true,
    }))

    try {
      const response = await sendMessage(message, currentSessionId, webSearchEnabled)
      // 后端返回的是 { session_id, user_message, assistant_message }
      const replyContent = response?.assistant_message?.content
        || response?.data?.assistant_message?.content
        || '抱歉，我没有理解您的问题。'

      const assistantMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: replyContent,
        timestamp: new Date().toISOString(),
      }

      set((state) => ({
        messages: state.messages.map((m) =>
          m.id === msgId ? { ...m, status: 'sent' } : m
        ).concat(assistantMessage),
        currentSessionId: response.session_id || response?.data?.session_id || state.currentSessionId,
        loading: false,
      }))

      get().fetchSessions()
    } catch (error) {
      set((state) => ({
        messages: state.messages.map((m) =>
          m.id === msgId ? { ...m, status: 'failed' } : m
        ),
        error: error.message,
        loading: false,
      }))
    }
  },

  // 重试发送失败的消息
  retryMessage: async (msgId) => {
    const { messages, currentSessionId } = get()
    const failedMsg = messages.find((m) => m.id === msgId)
    if (!failedMsg || failedMsg.status !== 'failed') return

    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === msgId ? { ...m, status: 'sending' } : m
      ),
      loading: true,
    }))

    try {
      const response = await sendMessage(failedMsg.content, currentSessionId, get().webSearchEnabled)
      // 后端返回的是 { session_id, user_message, assistant_message }
      const replyContent = response?.assistant_message?.content
        || response?.data?.assistant_message?.content
        || '抱歉，我没有理解您的问题。'

      const assistantMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: replyContent,
        timestamp: new Date().toISOString(),
      }

      set((state) => ({
        messages: state.messages.map((m) =>
          m.id === msgId ? { ...m, status: 'sent' } : m
        ).concat(assistantMessage),
        currentSessionId: response.session_id || response?.data?.session_id || state.currentSessionId,
        loading: false,
      }))

      get().fetchSessions()
    } catch (error) {
      set((state) => ({
        messages: state.messages.map((m) =>
          m.id === msgId ? { ...m, status: 'failed' } : m
        ),
        error: error.message,
        loading: false,
      }))
    }
  },

  // 创建新会话
  createNewSession: () => {
    set({ currentSessionId: null, messages: [], error: null })
  },

  // 删除会话
  removeSession: async (sessionId) => {
    try {
      await deleteSession(sessionId)
      set((state) => ({
        sessions: state.sessions.filter((s) => s.session_id !== sessionId),
        ...(state.currentSessionId === sessionId
          ? { currentSessionId: null, messages: [] }
          : {}),
      }))
      message.success('会话已删除')
    } catch (error) {
      message.error(error.message || '删除失败')
    }
  },

  // 清除错误
  clearError: () => {
    set({ error: null })
  },

  // 重置所有状态（切换账号时必须调用）
  resetStore: () => {
    set({
      sessions: [],
      currentSessionId: null,
      messages: [],
      loading: false,
      sessionsLoading: false,
      error: null,
    })
  },
}))

export default useChatStore
