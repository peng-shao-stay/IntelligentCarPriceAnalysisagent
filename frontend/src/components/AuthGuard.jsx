import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { message } from 'antd'

/**
 * 认证守卫组件
 * - 未登录 → 重定向到 /login
 * - adminOnly=true 且非 admin → 重定向到 /chat
 */
function AuthGuard({ children, adminOnly = false }) {
  const location = useLocation()

  const token = localStorage.getItem('auth_token')
  const userInfoStr = localStorage.getItem('user_info')

  if (!token || !userInfoStr) {
    message.warning('请先登录')
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (adminOnly) {
    try {
      const userInfo = JSON.parse(userInfoStr)
      if (userInfo.role !== 'admin') {
        message.error('无权访问管理后台')
        return <Navigate to="/chat" replace />
      }
    } catch {
      return <Navigate to="/login" replace />
    }
  }

  return children
}

export default AuthGuard
