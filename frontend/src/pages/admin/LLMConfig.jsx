import React, { useEffect, useState, useCallback } from 'react'
import {
  Card, Form, Input, InputNumber, Slider, Button, Switch,
  Tag, message, Spin, Row, Col, Alert, Space, Typography, Popconfirm,
  Descriptions,
} from 'antd'
import {
  CloudOutlined, DesktopOutlined,
  CheckCircleOutlined, CloseCircleOutlined,
  ThunderboltOutlined, SaveOutlined, ReloadOutlined,
  PlayCircleOutlined, ExclamationCircleOutlined,
} from '@ant-design/icons'
import {
  fetchLLMConfig, updateLLMConfig,
  testLLMConnection, switchLLMModel,
} from '../../api/admin'
import { useTheme } from '../../context/ThemeContext'

const { Text, Title } = Typography

function LLMConfig() {
  const { dark } = useTheme()
  const [config, setConfig] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(null)  // 'cloud' | 'local' | null
  const [testing, setTesting] = useState(null) // 'cloud' | 'local' | null
  const [switching, setSwitching] = useState(false)
  const [testResults, setTestResults] = useState({})

  const [cloudForm] = Form.useForm()
  const [localForm] = Form.useForm()

  const loadConfig = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchLLMConfig()
      setConfig(result)
      cloudForm.setFieldsValue({
        api_key: '',
        base_url: result.cloud.base_url,
        model_name: result.cloud.model_name,
        temperature: result.cloud.temperature,
        max_tokens: result.cloud.max_tokens,
      })
      localForm.setFieldsValue({
        base_url: result.local.base_url,
        model_name: result.local.model_name,
        temperature: result.local.temperature,
      })
    } catch (err) {
      setError(err.message || '加载配置失败')
    } finally {
      setLoading(false)
    }
  }, [cloudForm, localForm])

  useEffect(() => { loadConfig() }, [loadConfig])

  const saveConfig = async (backend) => {
    const form = backend === 'cloud' ? cloudForm : localForm
    try {
      const values = await form.validateFields()
      setSaving(backend)
      const payload = {}
      if (backend === 'cloud') {
        payload.cloud = {
          api_key: values.api_key || undefined,
          base_url: values.base_url,
          model_name: values.model_name,
          temperature: values.temperature,
          max_tokens: values.max_tokens,
        }
      } else {
        payload.local = {
          base_url: values.base_url,
          model_name: values.model_name,
          temperature: values.temperature,
        }
      }
      await updateLLMConfig(payload)
      message.success(`${backend === 'cloud' ? '云端' : '本地'} LLM 配置已保存`)
      setTestResults(prev => { const n = { ...prev }; delete n[backend]; return n })
      await loadConfig()
    } catch (err) {
      if (err.errorFields) return
      message.error(err.message || '保存失败')
    } finally {
      setSaving(null)
    }
  }

  const handleTestConnection = async (backend) => {
    const form = backend === 'cloud' ? cloudForm : localForm
    try {
      const formValues = await form.validateFields()
      setTesting(backend)
      const params = {
        backend,
        base_url: formValues.base_url,
        model_name: formValues.model_name,
      }
      // For cloud, include api_key from form or fall back to masked config value
      if (backend === 'cloud') {
        params.api_key = formValues.api_key || undefined
      }
      const result = await testLLMConnection(params)
      setTestResults(prev => ({ ...prev, [backend]: result }))
      if (result.success) {
        message.success(`${backend === 'cloud' ? '云端' : '本地'}连接成功 (${result.latency_ms}ms)`)
      } else {
        message.error(result.message)
      }
    } catch (err) {
      if (err.errorFields) return
      setTestResults(prev => ({
        ...prev,
        [backend]: { success: false, latency_ms: 0, message: err.message },
      }))
    } finally {
      setTesting(null)
    }
  }

  const handleSwitchModel = async (targetModel) => {
    setSwitching(true)
    try {
      await switchLLMModel(targetModel)
      message.success(`已切换至 ${targetModel === 'primary' ? '云端 DeepSeek' : '本地 Ollama'}`)
      await loadConfig()
    } catch (err) {
      message.error(err.message || '切换失败')
    } finally {
      setSwitching(false)
    }
  }

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>
  }

  const cardBg = dark ? '#1f1f1f' : '#fff'
  const textColor = dark ? '#e0e0e0' : '#333'
  const isCloudActive = config?.default_model === 'primary'
  const isLocalActive = config?.default_model === 'assistant'
  const cloudConfigured = config?.cloud?.api_key && config.cloud.api_key.length > 4

  return (
    <div style={{ color: textColor }}>
      <Title level={2} style={{ marginBottom: 24 }}>LLM 模型配置</Title>

      {error && (
        <Alert
          type="error"
          message="加载失败"
          description={error}
          showIcon
          closable
          style={{ marginBottom: 16 }}
          action={<Button size="small" onClick={loadConfig} icon={<ReloadOutlined />}>重试</Button>}
        />
      )}

      {/* ── 模型切换卡片 ── */}
      <Card
        title={<Space><ThunderboltOutlined /> 当前模型</Space>}
        style={{ background: cardBg, marginBottom: 16 }}
      >
        <Row gutter={[24, 16]} align="middle">
          <Col xs={24} sm={9}>
            <Card
              size="small"
              style={{
                background: isCloudActive ? (dark ? '#0d2137' : '#e6f4ff') : cardBg,
                border: isCloudActive ? '2px solid #1677ff' : `1px solid ${dark ? '#303030' : '#d9d9d9'}`,
              }}
            >
              <Space direction="vertical" style={{ width: '100%' }}>
                <Space>
                  <CloudOutlined style={{ fontSize: 24, color: '#1677ff' }} />
                  <Text strong>云端模型</Text>
                  {cloudConfigured ? <Tag color="green">已配置</Tag> : <Tag color="red">未配置</Tag>}
                </Space>
                <Text type="secondary" style={{ fontSize: 12 }}>{config?.cloud?.model_name || '-'}</Text>
                <Text type="secondary" style={{ fontSize: 12 }}>{config?.cloud?.base_url || '-'}</Text>
                {isCloudActive && <Tag color="blue" style={{ marginTop: 8 }}>当前使用中</Tag>}
                {!isCloudActive && (
                  <Popconfirm
                    title="确定切换到云端模型？"
                    onConfirm={() => handleSwitchModel('primary')}
                    okText="确定" cancelText="取消"
                  >
                    <Button type="primary" size="small" loading={switching} icon={<ThunderboltOutlined />}>
                      切换至此
                    </Button>
                  </Popconfirm>
                )}
              </Space>
            </Card>
          </Col>

          <Col xs={24} sm={9}>
            <Card
              size="small"
              style={{
                background: isLocalActive ? (dark ? '#14261a' : '#f6ffed') : cardBg,
                border: isLocalActive ? '2px solid #52c41a' : `1px solid ${dark ? '#303030' : '#d9d9d9'}`,
              }}
            >
              <Space direction="vertical" style={{ width: '100%' }}>
                <Space>
                  <DesktopOutlined style={{ fontSize: 24, color: '#52c41a' }} />
                  <Text strong>本地模型</Text>
                  {config?.local?.base_url ? <Tag color="green">已配置</Tag> : <Tag color="red">未配置</Tag>}
                </Space>
                <Text type="secondary" style={{ fontSize: 12 }}>{config?.local?.model_name || '-'}</Text>
                <Text type="secondary" style={{ fontSize: 12 }}>{config?.local?.base_url || '-'}</Text>
                {isLocalActive && <Tag color="green" style={{ marginTop: 8 }}>当前使用中</Tag>}
                {!isLocalActive && (
                  <Popconfirm
                    title="确定切换到本地模型？"
                    onConfirm={() => handleSwitchModel('assistant')}
                    okText="确定" cancelText="取消"
                  >
                    <Button
                      type="primary" size="small" loading={switching}
                      icon={<ThunderboltOutlined />}
                      style={{ background: '#52c41a', borderColor: '#52c41a' }}
                    >
                      切换至此
                    </Button>
                  </Popconfirm>
                )}
              </Space>
            </Card>
          </Col>

          <Col xs={24} sm={6}>
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="默认模型">
                <Tag color={isCloudActive ? 'blue' : 'green'}>
                  {isCloudActive ? 'DeepSeek (云端)' : 'Ollama (本地)'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="云端状态">
                {cloudConfigured ? (
                  <Space><CheckCircleOutlined style={{ color: '#52c41a' }} /><Text type="success">已配置</Text></Space>
                ) : (
                  <Space><CloseCircleOutlined style={{ color: '#ff4d4f' }} /><Text type="danger">需要 API Key</Text></Space>
                )}
              </Descriptions.Item>
              <Descriptions.Item label="本地状态">
                {config?.local?.base_url ? (
                  <Space><CheckCircleOutlined style={{ color: '#52c41a' }} /><Text type="success">已配置</Text></Space>
                ) : (
                  <Space><CloseCircleOutlined style={{ color: '#ff4d4f' }} /><Text type="danger">待配置</Text></Space>
                )}
              </Descriptions.Item>
            </Descriptions>
          </Col>
        </Row>
      </Card>

      {/* ── 云端 LLM 配置 ── */}
      <Card
        title={<Space><CloudOutlined /> 云端 LLM 配置 (DeepSeek)</Space>}
        style={{ background: cardBg, marginBottom: 16 }}
        extra={
          <Space>
            <Button
              icon={<PlayCircleOutlined />}
              onClick={() => handleTestConnection('cloud')}
              loading={testing === 'cloud'}
            >
              测试连接
            </Button>
            <Button
              type="primary" icon={<SaveOutlined />}
              onClick={() => saveConfig('cloud')}
              loading={saving === 'cloud'}
            >
              保存
            </Button>
          </Space>
        }
      >
        <Form form={cloudForm} layout="vertical">
          <Row gutter={[16, 0]}>
            <Col xs={24} md={12}>
              <Form.Item
                name="api_key"
                label="API Key"
                extra={config?.cloud?.api_key ? `已存: ${config.cloud.api_key}  |  留空则使用已保存的 Key` : '请输入 API Key'}
              >
                <Input.Password placeholder={config?.cloud?.api_key ? '留空使用已保存的 Key' : 'sk-...'} />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item
                name="base_url"
                label="API Base URL"
                rules={[{ required: true, message: '请输入 API Base URL' }]}
              >
                <Input placeholder="https://api.deepseek.com/v1" />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item
                name="model_name"
                label="模型名称"
                rules={[{ required: true, message: '请输入模型名称' }]}
              >
                <Input placeholder="deepseek-chat" />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item
                name="temperature"
                label="Temperature"
              >
                <Slider min={0} max={2} step={0.1} marks={{ 0: '0', 0.7: '0.7', 1: '1', 2: '2' }} />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item
                name="max_tokens"
                label="Max Tokens"
              >
                <InputNumber min={1} max={128000} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
        </Form>

        {testResults.cloud && (
          <Alert
            type={testResults.cloud.success ? 'success' : 'error'}
            message={testResults.cloud.success ? '连接成功' : '连接失败'}
            description={
              <div>
                <p>{testResults.cloud.message}</p>
                {testResults.cloud.key_source && (
                  <p>Key 来源: {testResults.cloud.key_source === 'stored' ? '已保存的 Key' : '表单中输入的 Key'}</p>
                )}
                {testResults.cloud.success && <p>延迟: {testResults.cloud.latency_ms}ms</p>}
              </div>
            }
            showIcon
            closable
            style={{ marginTop: 12 }}
          />
        )}
      </Card>

      {/* ── 本地 LLM 配置 ── */}
      <Card
        title={<Space><DesktopOutlined /> 本地 LLM 配置 (Ollama)</Space>}
        style={{ background: cardBg, marginBottom: 16 }}
        extra={
          <Space>
            <Button
              icon={<PlayCircleOutlined />}
              onClick={() => handleTestConnection('local')}
              loading={testing === 'local'}
            >
              测试连接
            </Button>
            <Button
              type="primary" icon={<SaveOutlined />}
              onClick={() => saveConfig('local')}
              loading={saving === 'local'}
            >
              保存
            </Button>
          </Space>
        }
      >
        <Form form={localForm} layout="vertical">
          <Row gutter={[16, 0]}>
            <Col xs={24} md={12}>
              <Form.Item
                name="base_url"
                label="Ollama Base URL"
                rules={[{ required: true, message: '请输入 Ollama Base URL' }]}
              >
                <Input placeholder="http://localhost:11434" />
              </Form.Item>
            </Col>
            <Col xs={24} md={6}>
              <Form.Item
                name="model_name"
                label="模型名称"
                rules={[{ required: true, message: '请输入模型名称' }]}
              >
                <Input placeholder="qwen3.5:9b" />
              </Form.Item>
            </Col>
            <Col xs={24} md={6}>
              <Form.Item
                name="temperature"
                label="Temperature"
              >
                <Slider min={0} max={2} step={0.1} marks={{ 0: '0', 0.7: '0.7', 1: '1', 2: '2' }} />
              </Form.Item>
            </Col>
          </Row>
        </Form>

        {testResults.local && (
          <Alert
            type={testResults.local.success ? 'success' : 'error'}
            message={testResults.local.success ? '连接成功' : '连接失败'}
            description={
              <div>
                <p>{testResults.local.message}</p>
                {testResults.local.success && <p>延迟: {testResults.local.latency_ms}ms</p>}
              </div>
            }
            showIcon
            closable
            style={{ marginTop: 12 }}
          />
        )}
      </Card>
    </div>
  )
}

export default LLMConfig
