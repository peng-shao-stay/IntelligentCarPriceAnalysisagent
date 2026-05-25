import React, { useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ConfigProvider, theme } from 'antd'
import { ThemeContext } from './context/ThemeContext'
import LoginPage from './pages/LoginPage'
import ChatPage from './pages/ChatPage'
import AdminLayout from './pages/admin/AdminLayout'
import Dashboard from './pages/admin/Dashboard'
import UserManagement from './pages/admin/UserManagement'
import DataListPage from './pages/DataListPage'
import LLMConfig from './pages/admin/LLMConfig'
import RAGManager from './pages/admin/RAGManager'
import AuthGuard from './components/AuthGuard'
import ErrorBoundary from './components/ErrorBoundary'

function App() {
  const [dark, setDark] = useState(localStorage.getItem('theme') === 'dark')

  const toggleTheme = () => {
    setDark((prev) => {
      const next = !prev
      localStorage.setItem('theme', next ? 'dark' : 'light')
      return next
    })
  }

  return (
    <ThemeContext.Provider value={{ dark, toggleTheme }}>
      <ConfigProvider theme={{ algorithm: dark ? theme.darkAlgorithm : theme.defaultAlgorithm }}>
        <ErrorBoundary>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<LoginPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/chat" element={<AuthGuard><ChatPage /></AuthGuard>} />
              <Route path="/admin" element={<AuthGuard adminOnly><AdminLayout /></AuthGuard>}>
                <Route index element={<Dashboard />} />
                <Route path="users" element={<UserManagement />} />
                <Route path="data" element={<DataListPage />} />
                <Route path="llm" element={<LLMConfig />} />
                <Route path="rag" element={<RAGManager />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </ErrorBoundary>
      </ConfigProvider>
    </ThemeContext.Provider>
  )
}

export default App
