import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器 - 自动附加认证令牌
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    let detail = error.response?.data?.detail
      || error.response?.data?.message
      || error.message

    // FastAPI 422 validation errors: detail is an array of {loc, msg, type}
    if (Array.isArray(detail)) {
      detail = detail.map(e => `${e.msg || e.message || JSON.stringify(e)}`).join('; ')
    }

    const enriched = new Error(detail)
    enriched.status = error.response?.status
    enriched.originalError = error
    return Promise.reject(enriched)
  }
)

export default api