import api from './index'

// 仪表盘
export const fetchDashboardStats = () => api.get('/admin/stats')
export const fetchMessageTrend = (days = 7) => api.get('/admin/trend', { params: { days } })
export const fetchRecentActivity = (limit = 10) => api.get('/admin/activity', { params: { limit } })

// 用户管理
export const fetchUsers = (params) => api.get('/admin/users', { params })
export const updateUserRole = (userId, role) => api.put(`/admin/users/${userId}/role`, { role })
export const toggleUserStatus = (userId) => api.put(`/admin/users/${userId}/status`)
export const deleteUser = (userId) => api.delete(`/admin/users/${userId}`)

// LLM 配置
export const fetchLLMConfig = () => api.get('/admin/llm-config')
export const updateLLMConfig = (data) => api.put('/admin/llm-config', data)
export const testLLMConnection = (data) => api.post('/admin/llm-config/test', data)
export const switchLLMModel = (modelType) => api.put('/admin/llm-config/switch', { model_type: modelType })

// RAG 知识库管理
export const fetchRAGStats = () => api.get('/admin/rag/stats')
export const fetchRAGDocuments = (params) => api.get('/admin/rag/documents', { params })
export const ingestRAGCar = (data) => api.post('/admin/rag/ingest', data)
export const ingestRAGBatch = (data) => api.post('/admin/rag/ingest/batch', data)
export const deleteRAGDocument = (docId) => api.delete(`/admin/rag/documents/${docId}`)
export const reindexRAGSample = () => api.post('/admin/rag/reindex')

// RAG 文件上传
export const uploadRAGFile = (file, onProgress) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/admin/rag/import/file', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
    onUploadProgress: onProgress,
  })
}
