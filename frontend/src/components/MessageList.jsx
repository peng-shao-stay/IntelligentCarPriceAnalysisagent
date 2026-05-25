import React, { useEffect, useRef } from 'react'
import { Avatar, Button } from 'antd'
import { UserOutlined, RobotOutlined, ReloadOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import useChatStore from '../stores/useChatStore'
import '../styles/MessageList.css'

function MessageList({ messages }) {
  const bottomRef = useRef(null)
  const retryMessage = useChatStore((s) => s.retryMessage)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="message-list">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`message-item ${msg.role === 'user' ? 'user-message' : 'assistant-message'}`}
        >
          <Avatar
            icon={msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
            style={{
              backgroundColor: msg.role === 'user' ? '#1890ff' : '#52c41a',
            }}
          />
          <div className="message-content">
            <div className="message-text">{msg.content}</div>
            <div className="message-meta">
              <span className="message-time">
                {dayjs(msg.created_at || msg.timestamp).format('YYYY-MM-DD HH:mm:ss')}
              </span>
              {msg.role === 'user' && msg.status === 'failed' && (
                <Button
                  type="link"
                  size="small"
                  icon={<ReloadOutlined />}
                  onClick={() => retryMessage(msg.id)}
                  className="retry-button"
                >
                  重试
                </Button>
              )}
              {msg.role === 'user' && msg.status === 'sending' && (
                <span className="sending-indicator">发送中...</span>
              )}
            </div>
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}

export default MessageList
