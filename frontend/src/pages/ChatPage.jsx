import React, { useEffect, useState } from 'react'
import { Layout, Input, Button, message as antdMessage, Spin, Empty, Avatar, Dropdown, Switch } from 'antd'
import { SendOutlined, LogoutOutlined, UserOutlined, DatabaseOutlined, GlobalOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { logout } from '../api/auth'
import useChatStore from '../stores/useChatStore'
import Sidebar from '../components/Sidebar'
import MessageList from '../components/MessageList'
import '../styles/ChatPage.css'

const { Header, Content, Sider } = Layout
const { TextArea } = Input

function ChatPage() {
  const navigate = useNavigate()
  const [inputValue, setInputValue] = useState('')
  const {
    messages,
    loading,
    error,
    webSearchEnabled,
    setWebSearchEnabled,
    sendUserMessage,
    fetchSessions,
    clearError,
    resetStore,
  } = useChatStore()
  
  // 获取用户信息
  const userInfo = JSON.parse(localStorage.getItem('user_info') || '{}')

  useEffect(() => {
    fetchSessions()
  }, [])

  useEffect(() => {
    if (error) {
      antdMessage.error(error)
      clearError()
    }
  }, [error])
  
  // 处理登出
  const handleLogout = async () => {
    try {
      await logout()
      resetStore()
      antdMessage.success('已退出登录')
      navigate('/login')
    } catch (error) {
      antdMessage.error('退出失败')
    }
  }
  
  // 用户菜单
  const userMenuItems = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
    },
  ]

  const handleSend = async () => {
    if (!inputValue.trim()) return
    
    await sendUserMessage(inputValue.trim())
    setInputValue('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <Layout style={{ height: '100vh' }}>
      <Sider width={280} theme="light" className="chat-sider">
        <Sidebar />
      </Sider>
      
      <Layout>
        <Header className="chat-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <h2 style={{ margin: 0 }}>🚗 AutoMind AI - 智能汽车价格分析助手</h2>
            {userInfo.role === 'admin' && (
              <Button
                type="text"
                icon={<DatabaseOutlined />}
                onClick={() => navigate('/admin')}
                style={{ color: 'white' }}
              >
                管理后台
              </Button>
            )}
          </div>
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px',
              cursor: 'pointer',
              color: 'white',
              padding: '4px 8px',
              borderRadius: '4px',
              transition: 'background 0.3s',
            }}
            onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.1)'}
            onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
            >
              <Avatar icon={<UserOutlined />} size="small" />
              <span>{userInfo.username || '用户'}</span>
            </div>
          </Dropdown>
        </Header>
        
        <Content className="chat-content">
          <div className="messages-container">
            {messages.length === 0 ? (
              <Empty
                description="开始新的对话，询问汽车价格相关信息"
                style={{ marginTop: 100 }}
              />
            ) : (
              <MessageList messages={messages} />
            )}
            
            {loading && (
              <div className="loading-indicator">
                <Spin tip="AI 正在思考..." />
              </div>
            )}
          </div>
          
          <div className="input-area">
            <TextArea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入您的问题...（Shift+Enter 换行）"
              autoFocus
              autoSize={{ minRows: 1, maxRows: 4 }}
              disabled={loading}
              className="chat-input"
            />
            <div className="input-actions">
              <Switch
                checked={webSearchEnabled}
                onChange={setWebSearchEnabled}
                checkedChildren={<><GlobalOutlined /> 联网</>}
                unCheckedChildren="本地"
                style={{ minWidth: 88 }}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSend}
                loading={loading}
                disabled={!inputValue.trim()}
                className="send-button"
              >
                发送
              </Button>
            </div>
          </div>
        </Content>
      </Layout>
    </Layout>
  )
}

export default ChatPage
