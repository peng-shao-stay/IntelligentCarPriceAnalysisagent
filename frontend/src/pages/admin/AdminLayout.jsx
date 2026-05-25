import React, { useState } from 'react'
import { Layout, Menu, Button, Input, Badge, Avatar, Dropdown, Switch, theme } from 'antd'
import {
  DashboardOutlined, UserOutlined, TeamOutlined,
  MenuFoldOutlined, MenuUnfoldOutlined,
  SearchOutlined, BellOutlined, LogoutOutlined,
  SettingOutlined, SunOutlined, MoonOutlined,
  DatabaseOutlined, ArrowLeftOutlined, ApiOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation, Outlet } from 'react-router-dom'
import { useTheme } from '../../context/ThemeContext'

const { Header, Sider, Content } = Layout

const menuItems = [
  { key: '/admin', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/admin/users', icon: <TeamOutlined />, label: '用户管理' },
  { key: '/admin/data', icon: <DatabaseOutlined />, label: '数据管理' },
  { key: '/admin/llm', icon: <ApiOutlined />, label: 'LLM配置' },
  { key: '/admin/rag', icon: <DatabaseOutlined />, label: '知识库' },
  ]

function AdminLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)
  const { dark, toggleTheme } = useTheme()
  const { token: themeToken } = theme.useToken()

  const userInfo = JSON.parse(localStorage.getItem('user_info') || '{}')

  const handleLogout = () => {
    localStorage.clear()
    navigate('/login')
  }

  const userMenuItems = [
    { key: 'profile', icon: <UserOutlined />, label: '个人信息' },
    { key: 'settings', icon: <SettingOutlined />, label: '系统设置' },
    { type: 'divider' },
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', onClick: handleLogout },
  ]

  const selectedKey = '/' + location.pathname.split('/').slice(1, 3).join('/')

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
          trigger={null}
          collapsible
          collapsed={collapsed}
          width={240}
          style={{
            background: dark ? '#141414' : '#001529',
            borderRight: dark ? '1px solid #303030' : 'none',
          }}
        >
          <div style={{
            height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center',
            borderBottom: `1px solid ${dark ? '#303030' : 'rgba(255,255,255,0.1)'}`,
          }}>
            <h2 style={{
              color: '#fff', margin: 0, fontSize: collapsed ? 16 : 18,
              whiteSpace: 'nowrap', overflow: 'hidden',
            }}>
              {collapsed ? '🚗' : '🚗 AutoMind'}
            </h2>
          </div>
          <Menu
            theme={dark ? 'dark' : 'dark'}
            mode="inline"
            selectedKeys={[selectedKey]}
            items={menuItems}
            onClick={({ key }) => navigate(key)}
          />
        </Sider>

        <Layout>
          <Header style={{
            background: dark ? '#1f1f1f' : '#fff',
            padding: '0 24px', display: 'flex', alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: `1px solid ${dark ? '#303030' : '#f0f0f0'}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <Button
                type="text"
                icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
                onClick={() => setCollapsed(!collapsed)}
                style={{ fontSize: 16, width: 40, height: 40 }}
              />
              <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/chat')}>
                返回前台
              </Button>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <Input
                prefix={<SearchOutlined />}
                placeholder="搜索..."
                style={{ width: 200 }}
                size="small"
              />
              <Badge count={3} size="small">
                <BellOutlined style={{ fontSize: 18, cursor: 'pointer' }} />
              </Badge>
              <Switch
                checkedChildren={<MoonOutlined />}
                unCheckedChildren={<SunOutlined />}
                checked={dark}
                onChange={toggleTheme}
              />
              <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                  <Avatar icon={<UserOutlined />} size="small" />
                  <span>{userInfo.username || 'Admin'}</span>
                </div>
              </Dropdown>
            </div>
          </Header>

          <Content style={{
            margin: 16, padding: 24,
            background: dark ? '#141414' : '#f5f5f5',
            borderRadius: 8, minHeight: 280, overflow: 'auto',
          }}>
            <Outlet />
          </Content>
        </Layout>
      </Layout>
  )
}

export default AdminLayout
