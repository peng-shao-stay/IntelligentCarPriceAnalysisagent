import api from './index'
import axios from 'axios'

// 发送聊天消息
export const sendMessage = (message, sessionId = null, webSearch = false) => {
  return api.post('/chat/', {
    message,
    session_id: sessionId,
    web_search: webSearch,
  })
}

// 获取会话列表
export const getSessions = () => {
  return api.get('/chat/sessions')
}

// 获取会话消息
export const getSessionMessages = (sessionId) => {
  return api.get(`/chat/sessions/${sessionId}`)
}

// 删除会话
export const deleteSession = (sessionId) => {
  return api.delete(`/chat/sessions/${sessionId}`)
}

// 健康检查（根路径 /health，不在 /api/v1 下）
export const healthCheck = () => {
  return axios.get('/health')
}
