import api from './index'

export const getCaptcha = () => api.get('/auth/captcha')

export const register = (data) => api.post('/auth/register', data)

export const login = (data) => api.post('/auth/login', data)

export const verifyToken = (token) => api.post('/auth/verify-token', { token })

export const getCurrentUser = () => api.get('/auth/me')

export const logout = () => {
  localStorage.removeItem('auth_token')
  localStorage.removeItem('user_info')
  localStorage.removeItem('remember_me')
  return Promise.resolve()
}
