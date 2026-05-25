import React, { useEffect, useState } from 'react'
import {
  Card, Table, Button, Modal, Form, Input, Select, InputNumber,
  Switch, message, Popconfirm, Space, Tag, Tooltip, Row, Col, Typography,
} from 'antd'
import {
  PlusOutlined, ApiOutlined, DeleteOutlined,
  ReloadOutlined, LinkOutlined, SearchOutlined,
  CheckCircleOutlined, CloseCircleOutlined,
} from '@ant-design/icons'
import {
  fetchMCPServers, createMCPServer, updateMCPServer,
  deleteMCPServer, testMCPConnection, fetchMCPTools,
} from '../../api/mcp'

const { TextArea } = Input
const { Text } = Typography

const TRANSPORT_OPTIONS = [
  { label: 'HTTP', value: 'http' },
  { label: 'SSE', value: 'sse' },
  { label: 'STDIO', value: 'stdio' },
]

const AUTH_OPTIONS = [
  { label: '无认证', value: 'none' },
  { label: 'Bearer Token', value: 'bearer' },
  { label: 'API Key', value: 'api_key' },
  { label: 'OAuth 2.0', value: 'oauth2' },
]

function MCPManager() {
  const [servers, setServers] = useState([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingServer, setEditingServer] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [testing, setTesting] = useState({})   // server_id -> bool
  const [toolsModal, setToolsModal] = useState(null)  // server record
  const [tools, setTools] = useState([])
  const [toolsLoading, setToolsLoading] = useState(false)
  const [form] = Form.useForm()

  const loadServers = async () => {
    setLoading(true)
    try {
      const res = await fetchMCPServers()
      setServers(res || [])
    } catch (e) {
      message.error('加载 MCP 服务器列表失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    loadServers()
    return () => controller.abort()
  }, [])

  // ── Modal handlers ──────────────────────────────────────

  const openCreateModal = () => {
    setEditingServer(null)
    form.resetFields()
    form.setFieldsValue({
      transport: 'http',
      auth_type: 'none',
      is_enabled: true,
      is_essential: false,
      timeout_seconds: 30,
      max_retries: 2,
    })
    setModalOpen(true)
  }

  const openEditModal = (record) => {
    setEditingServer(record)
    form.setFieldsValue(record)
    setModalOpen(true)
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      setSubmitting(true)
      if (editingServer) {
        await updateMCPServer(editingServer.id, values)
        message.success(`MCP 服务器 '${editingServer.name}' 已更新`)
      } else {
        await createMCPServer(values)
        message.success(`MCP 服务器 '${values.name}' 已创建`)
      }
      setModalOpen(false)
      loadServers()
    } catch (e) {
      if (e.errorFields) return  // form validation
      message.error('保存失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (record) => {
    try {
      await deleteMCPServer(record.id)
      message.success(`已删除 MCP 服务器 '${record.name}'`)
      loadServers()
    } catch (e) {
      message.error('删除失败: ' + (e.response?.data?.detail || e.message))
    }
  }

  const handleToggleEnabled = async (record, checked) => {
    try {
      await updateMCPServer(record.id, { is_enabled: checked })
      message.success(`已${checked ? '启用' : '禁用'} '${record.name}'`)
      loadServers()
    } catch (e) {
      message.error('操作失败: ' + (e.response?.data?.detail || e.message))
    }
  }

  // ── Test connection ─────────────────────────────────────

  const handleTestConnection = async (record) => {
    setTesting((prev) => ({ ...prev, [record.id]: true }))
    try {
      const res = await testMCPConnection(record.id)
      if (res.success) {
        message.success(`${res.message} (${res.latency_ms}ms)`)
        loadServers() // refresh tool schemas
      } else {
        message.warning(res.message)
      }
    } catch (e) {
      message.error('测试连接失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setTesting((prev) => ({ ...prev, [record.id]: false }))
    }
  }

  // ── View tools ──────────────────────────────────────────

  const handleViewTools = async (record) => {
    setToolsModal(record)
    setToolsLoading(true)
    try {
      const res = await fetchMCPTools(record.id)
      setTools(res.tools || [])
    } catch (e) {
      message.error('获取工具列表失败: ' + (e.response?.data?.detail || e.message))
      setTools([])
    } finally {
      setToolsLoading(false)
    }
  }

  // ── Columns ─────────────────────────────────────────────

  const columns = [
    {
      title: '服务器名称',
      dataIndex: 'name',
      key: 'name',
      width: 160,
      render: (text, record) => (
        <Space>
          <ApiOutlined style={{ color: record.is_enabled ? '#52c41a' : '#d9d9d9' }} />
          <span>
            {text}
            {record.is_essential && (
              <Tag color="blue" style={{ marginLeft: 8 }}>必需</Tag>
            )}
          </span>
        </Space>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (text) => text || '—',
    },
    {
      title: '传输协议',
      dataIndex: 'transport',
      key: 'transport',
      width: 90,
      render: (v) => <Tag>{v?.toUpperCase()}</Tag>,
    },
    {
      title: '地址',
      dataIndex: 'base_url',
      key: 'base_url',
      width: 220,
      ellipsis: true,
      render: (text) => text || '—',
    },
    {
      title: '认证',
      dataIndex: 'auth_type',
      key: 'auth_type',
      width: 90,
      render: (v) => {
        const labels = { none: '无', bearer: 'Bearer', api_key: 'API Key', oauth2: 'OAuth2' }
        return <Tag color={v === 'none' ? 'default' : 'orange'}>{labels[v] || v}</Tag>
      },
    },
    {
      title: '工具数',
      dataIndex: 'tool_schemas',
      key: 'tool_count',
      width: 75,
      align: 'center',
      render: (schemas) => {
        const count = Array.isArray(schemas) ? schemas.length : 0
        return (
          <Tooltip title={count > 0 ? schemas.map((t) => t.name).join(', ') : '未发现'}>
            <Tag color={count > 0 ? 'green' : 'default'}>{count}</Tag>
          </Tooltip>
        )
      },
    },
    {
      title: '状态',
      dataIndex: 'is_enabled',
      key: 'is_enabled',
      width: 70,
      align: 'center',
      render: (enabled, record) => (
        <Switch
          checked={enabled}
          disabled={record.is_essential}
          onChange={(checked) => handleToggleEnabled(record, checked)}
          size="small"
        />
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 260,
      render: (_, record) => (
        <Space size="small">
          <Button
            size="small"
            icon={<LinkOutlined />}
            loading={testing[record.id]}
            onClick={() => handleTestConnection(record)}
          >
            测试
          </Button>
          <Button
            size="small"
            icon={<SearchOutlined />}
            onClick={() => handleViewTools(record)}
          >
            工具
          </Button>
          <Button
            size="small"
            onClick={() => openEditModal(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除此 MCP 服务器？"
            description={record.is_essential ? '必需服务器不可删除' : undefined}
            onConfirm={() => handleDelete(record)}
            disabled={record.is_essential}
          >
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              disabled={record.is_essential}
            />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <>
      <Card
        title={
          <Space>
            <ApiOutlined />
            <span>MCP 服务器管理</span>
          </Space>
        }
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={loadServers} loading={loading}>
              刷新
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
              添加 MCP 服务器
            </Button>
          </Space>
        }
      >
        <Table
          dataSource={servers}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={false}
          locale={{ emptyText: '暂无 MCP 服务器配置，点击"添加 MCP 服务器"开始' }}
        />
      </Card>

      {/* ── Create / Edit Modal ──────────────────────────── */}
      <Modal
        title={editingServer ? `编辑 MCP 服务器: ${editingServer.name}` : '添加 MCP 服务器'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={submitting}
        width={640}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="name" label="服务器名称" rules={[{ required: true, message: '请输入名称' }]}>
                <Input placeholder="例如: car-data, rag-vector" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="transport" label="传输协议" rules={[{ required: true }]}>
                <Select options={TRANSPORT_OPTIONS} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="description" label="描述">
            <TextArea rows={2} placeholder="服务器用途描述" />
          </Form.Item>
          <Form.Item name="base_url" label="Base URL (HTTP/SSE)" rules={[
            ({ getFieldValue }) => ({
              validator(_, value) {
                const transport = getFieldValue('transport')
                if ((transport === 'http' || transport === 'sse') && !value) {
                  return Promise.reject('HTTP/SSE 传输需要填写 Base URL')
                }
                return Promise.resolve()
              },
            }),
          ]}>
            <Input placeholder="http://localhost:9000" />
          </Form.Item>
          <Form.Item name="command" label="启动命令 (STDIO)" rules={[
            ({ getFieldValue }) => ({
              validator(_, value) {
                if (getFieldValue('transport') === 'stdio' && !value) {
                  return Promise.reject('STDIO 传输需要填写启动命令')
                }
                return Promise.resolve()
              },
            }),
          ]}>
            <Input placeholder="python -m car_data_mcp.server" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="auth_type" label="认证方式">
                <Select options={AUTH_OPTIONS} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="timeout_seconds" label="超时 (秒)">
                <InputNumber min={5} max={300} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="is_enabled" label="启用" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="is_essential" label="必需服务 (不可禁用/删除)" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="max_retries" label="最大重试次数">
            <InputNumber min={0} max={5} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>

      {/* ── Tools Modal ───────────────────────────────────── */}
      <Modal
        title={toolsModal ? `工具列表: ${toolsModal.name}` : '工具列表'}
        open={!!toolsModal}
        onCancel={() => { setToolsModal(null); setTools([]) }}
        footer={null}
        width={700}
      >
        {toolsLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>加载中...</div>
        ) : tools.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
            暂无工具 — 请先点击"测试"按钮连接服务器
          </div>
        ) : (
          tools.map((tool, idx) => (
            <Card
              key={tool.name}
              size="small"
              style={{ marginBottom: 12 }}
              title={
                <Space>
                  <Tag color="blue">{idx + 1}</Tag>
                  <Text strong>{tool.name}</Text>
                  <Tag>{tool.server_name}</Tag>
                </Space>
              }
            >
              <Text type="secondary">{tool.description}</Text>
              {tool.input_schema && Object.keys(tool.input_schema).length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    参数: {JSON.stringify(tool.input_schema)}
                  </Text>
                </div>
              )}
            </Card>
          ))
        )}
      </Modal>
    </>
  )
}

export default MCPManager
