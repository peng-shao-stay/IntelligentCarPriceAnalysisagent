import React from 'react'
import { List, Button, Empty, Spin, message, Popconfirm } from 'antd'
import { PlusOutlined, MessageOutlined, CloseCircleFilled } from '@ant-design/icons'
import useChatStore from '../stores/useChatStore'
import '../styles/Sidebar.css'

function Sidebar() {
  const { sessions, currentSessionId, sessionsLoading, selectSession, createNewSession, removeSession } = useChatStore()

  const handleNewChat = () => {
    createNewSession()
    message.success('已创建新对话')
  }

  return (
    <div className="sidebar">
      <Button
        type="primary"
        icon={<PlusOutlined />}
        onClick={handleNewChat}
        block
        className="new-chat-button"
      >
        新对话
      </Button>

      <div className="sessions-list">
        {sessionsLoading ? (
          <div className="sessions-loading">
            <Spin />
          </div>
        ) : sessions.length === 0 ? (
          <Empty description="暂无会话" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <List
            dataSource={sessions}
            renderItem={(session) => (
              <List.Item
                className={`session-item ${session.session_id === currentSessionId ? 'active' : ''}`}
                onClick={() => selectSession(session.session_id)}
              >
                <MessageOutlined style={{ marginRight: 8, flexShrink: 0 }} />
                <span className="session-title">
                  {session.title || '未命名会话'}
                </span>
                <Popconfirm
                  title="确定删除此会话？"
                  description="删除后无法恢复"
                  onConfirm={(e) => {
                    e.stopPropagation()
                    removeSession(session.session_id)
                  }}
                  onCancel={(e) => e.stopPropagation()}
                  okText="删除"
                  cancelText="取消"
                  okButtonProps={{ danger: true }}
                >
                  <CloseCircleFilled
                    className="session-delete-icon"
                    onClick={(e) => e.stopPropagation()}
                  />
                </Popconfirm>
              </List.Item>
            )}
          />
        )}
      </div>
    </div>
  )
}

export default Sidebar
