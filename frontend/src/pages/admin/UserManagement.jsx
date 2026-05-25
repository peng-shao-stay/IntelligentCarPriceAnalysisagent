import React, { useEffect, useState, useCallback } from 'react'
import {
  Table, Input, Select, Button, Space, Tag, Popconfirm,
  message, Empty, Spin, Card, Row, Col, Switch,
} from 'antd'
import {
  SearchOutlined, ReloadOutlined, DeleteOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons'
import { fetchUsers, updateUserRole, toggleUserStatus, deleteUser } from '../../api/admin'
import { useTheme } from '../../context/ThemeContext'

function UserManagement() {
  const { dark } = useTheme()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [keyword, setKeyword] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const loadUsers = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchUsers({ page, page_size: pageSize, keyword, role: roleFilter, status: statusFilter })
      setUsers(result.items)
      setTotal(result.total)
    } catch (err) {
      setError(err.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, keyword, roleFilter, statusFilter])

  useEffect(() => { loadUsers() }, [loadUsers])

  const handleRoleToggle = async (user) => {
    const newRole = user.role === 'admin' ? 'user' : 'admin'
    try {
      await updateUserRole(user.id, newRole)
      message.success(`已将 ${user.username} 的角色改为 ${newRole === 'admin' ? '管理员' : '普通用户'}`)
      loadUsers()
    } catch (err) {
      message.error(err.message || '操作失败')
    }
  }

  const handleStatusToggle = async (user) => {
    try {
      await toggleUserStatus(user.id)
      message.success(`已${user.status === 'active' ? '禁用' : '启用'} ${user.username}`)
      loadUsers()
    } catch (err) {
      message.error(err.message || '操作失败')
    }
  }

  const handleDelete = async (user) => {
    try {
      await deleteUser(user.id)
      message.success(`已删除用户 ${user.username}`)
      loadUsers()
    } catch (err) {
      message.error(err.message || '删除失败')
    }
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 70 },
    { title: '用户名', dataIndex: 'username', width: 130, ellipsis: true },
    { title: '邮箱', dataIndex: 'email', width: 200, ellipsis: true,
      responsive: ['md'],
    },
    {
      title: '角色', dataIndex: 'role', width: 100,
      render: (role, record) => (
        <Popconfirm
          title={`确定将 ${record.username} 切换为${role === 'admin' ? '普通用户' : '管理员'}？`}
          onConfirm={() => handleRoleToggle(record)}
          okText="确定" cancelText="取消"
        >
          <Tag color={role === 'admin' ? 'gold' : 'blue'} style={{ cursor: 'pointer' }}>
            {role === 'admin' ? '管理员' : '普通用户'}
          </Tag>
        </Popconfirm>
      ),
    },
    {
      title: '状态', dataIndex: 'status', width: 90,
      render: (status, record) => (
        <Popconfirm
          title={`确定${status === 'active' ? '禁用' : '启用'} ${record.username}？`}
          onConfirm={() => handleStatusToggle(record)}
          okText="确定" cancelText="取消"
        >
          <Switch
            checked={status === 'active'}
            size="small"
            loading={false}
          />
        </Popconfirm>
      ),
    },
    {
      title: '注册时间', dataIndex: 'created_at', width: 170,
      responsive: ['lg'],
      render: (v) => v ? new Date(v).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作', key: 'actions', width: 100, fixed: 'right',
      render: (_, record) => (
        <Popconfirm
          title={`确定删除 ${record.username}？此操作不可撤销。`}
          onConfirm={() => handleDelete(record)}
          okText="确定" cancelText="取消"
          okType="danger"
        >
          <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
        </Popconfirm>
      ),
    },
  ]

  const cardBg = dark ? '#1f1f1f' : '#fff'

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>用户管理</h2>

      {/* 筛选栏 */}
      <Card style={{ background: cardBg, marginBottom: 16 }} size="small">
        <Row gutter={[16, 12]} align="middle">
          <Col xs={24} sm={8} md={6}>
            <Input
              placeholder="搜索用户名或邮箱"
              prefix={<SearchOutlined />}
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onPressEnter={() => { setPage(1); loadUsers() }}
              allowClear
            />
          </Col>
          <Col xs={12} sm={6} md={4}>
            <Select
              placeholder="角色筛选"
              value={roleFilter || undefined}
              onChange={(v) => { setRoleFilter(v || ''); setPage(1) }}
              allowClear
              style={{ width: '100%' }}
              options={[
                { label: '管理员', value: 'admin' },
                { label: '普通用户', value: 'user' },
              ]}
            />
          </Col>
          <Col xs={12} sm={6} md={4}>
            <Select
              placeholder="状态筛选"
              value={statusFilter || undefined}
              onChange={(v) => { setStatusFilter(v || ''); setPage(1) }}
              allowClear
              style={{ width: '100%' }}
              options={[
                { label: '正常', value: 'active' },
                { label: '已禁用', value: 'disabled' },
              ]}
            />
          </Col>
          <Col xs={24} sm={4} md={10}>
            <Space>
              <Button type="primary" icon={<SearchOutlined />} onClick={() => { setPage(1); loadUsers() }}>搜索</Button>
              <Button icon={<ReloadOutlined />} onClick={() => { setKeyword(''); setRoleFilter(''); setStatusFilter(''); setPage(1) }}>重置</Button>
            </Space>
          </Col>
        </Row>
      </Card>

      {/* 错误状态 */}
      {error && (
        <Card style={{ marginBottom: 16, background: '#fff2f0', border: '1px solid #ffccc7' }}>
          <div style={{ textAlign: 'center', padding: 20 }}>
            <ExclamationCircleOutlined style={{ fontSize: 32, color: '#ff4d4f', marginBottom: 12 }} />
            <p style={{ color: '#ff4d4f' }}>{error}</p>
            <Button type="primary" onClick={loadUsers}>重试</Button>
          </div>
        </Card>
      )}

      {/* 用户表格 */}
      <Card style={{ background: cardBg }} size="small">
        <Table
          rowKey="id"
          columns={columns}
          dataSource={users}
          loading={loading && users.length === 0}
          onChange={(p) => { setPage(p.current); setPageSize(p.pageSize) }}
          scroll={{ x: 800 }}
          locale={{ emptyText: <Empty description={keyword || roleFilter || statusFilter ? '没有匹配的用户' : '暂无用户'} /> }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 个用户`,
            pageSizeOptions: ['10', '20', '50'],
            responsive: true,
          }}
        />
      </Card>
    </div>
  )
}

export default UserManagement
