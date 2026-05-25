import React, { useEffect, useState } from 'react'
import {
  Card, Row, Col, Statistic, Table, Button, Modal, Form, Input,
  Select, message, Popconfirm, Space, Tag, Spin, Upload, Progress,
} from 'antd'
import {
  PlusOutlined, DatabaseOutlined, DeleteOutlined,
  ReloadOutlined, ExperimentOutlined, UploadOutlined,
} from '@ant-design/icons'
import {
  fetchRAGStats, fetchRAGDocuments, ingestRAGCar,
  deleteRAGDocument, reindexRAGSample, uploadRAGFile,
} from '../../api/admin'

const { TextArea } = Input

function RAGManager() {
  const [stats, setStats] = useState(null)
  const [docs, setDocs] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [form] = Form.useForm()

  const loadData = async () => {
    setLoading(true)
    try {
      const [statsRes, docsRes] = await Promise.all([
        fetchRAGStats(),
        fetchRAGDocuments({ limit: 100 }),
      ])
      setStats(statsRes)
      setDocs(docsRes.items || [])
      setTotal(docsRes.total || 0)
    } catch (e) {
      message.error('加载知识库数据失败: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [])

  const handleIngest = async () => {
    try {
      const values = await form.validateFields()
      setSubmitting(true)
      const res = await ingestRAGCar(values)
      message.success(res.message || '录入成功')
      setModalOpen(false)
      form.resetFields()
      loadData()
    } catch (e) {
      if (e.errorFields) return // form validation
      message.error('录入失败: ' + (e.message || '未知错误'))
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (id) => {
    try {
      await deleteRAGDocument(id)
      message.success('已删除')
      loadData()
    } catch (e) {
      message.error('删除失败: ' + e.message)
    }
  }

  const handleReindex = async () => {
    try {
      setLoading(true)
      const res = await reindexRAGSample()
      message.success(res.message || '录入完成')
      loadData()
    } catch (e) {
      message.error('录入失败: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleFileUpload = async (file) => {
    setUploading(true)
    setUploadProgress(0)
    try {
      const res = await uploadRAGFile(file, (e) => {
        if (e.total) {
          setUploadProgress(Math.round((e.loaded / e.total) * 100))
        }
      })
      message.success(res.message || `已导入: ${res.filename || file.name}`)
      setUploadModalOpen(false)
      setUploadProgress(0)
      loadData()
    } catch (e) {
      message.error('上传失败: ' + e.message)
    } finally {
      setUploading(false)
    }
    return false // prevent default antd Upload behavior
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '标题', dataIndex: 'title', ellipsis: true },
    { title: '品牌', dataIndex: 'brand', width: 80, render: (v) => v ? <Tag color="blue">{v}</Tag> : '-' },
    { title: '车型', dataIndex: 'model', width: 100 },
    { title: '年份', dataIndex: 'year', width: 60 },
    { title: '能源', dataIndex: 'energy_type', width: 80, render: (v) => v || '-' },
    {
      title: '来源', dataIndex: 'source_uri', width: 60,
      render: (v) => v ? <Tag color={v.includes('http') ? 'green' : 'default'}>链接</Tag> : '-',
    },
    {
      title: '操作', key: 'actions', width: 80,
      render: (_, record) => (
        <Popconfirm title="确定删除此文档？" onConfirm={() => handleDelete(record.id)} okText="删除" cancelText="取消">
          <Button type="text" danger icon={<DeleteOutlined />} size="small" />
        </Popconfirm>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2><DatabaseOutlined /> 本地知识库管理 (RAG)</h2>
        <Space>
          <Button icon={<ExperimentOutlined />} onClick={handleReindex} loading={loading}>
            录入示例数据
          </Button>
          <Button icon={<PlusOutlined />} type="primary" onClick={() => setModalOpen(true)}>
            录入车辆
          </Button>
          <Button icon={<UploadOutlined />} onClick={() => setUploadModalOpen(true)}>
            上传文档
          </Button>
          <Button icon={<ReloadOutlined />} onClick={loadData} loading={loading} />
        </Space>
      </div>

      {stats && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={4}>
            <Card><Statistic title="文档数" value={stats.document_count} prefix={<DatabaseOutlined />} /></Card>
          </Col>
          <Col span={4}>
            <Card><Statistic title="分块数" value={stats.chunk_count} /></Card>
          </Col>
          <Col span={4}>
            <Card><Statistic title="嵌入模型" value={stats.embedding_model} valueStyle={{ fontSize: 16 }} /></Card>
          </Col>
          <Col span={4}>
            <Card><Statistic title="向量维度" value={stats.embedding_dim} /></Card>
          </Col>
          <Col span={8}>
            <Card>
              <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>品牌列表</div>
              <Space wrap>{stats.brands?.map((b) => <Tag key={b} color="blue">{b}</Tag>)}</Space>
            </Card>
          </Col>
        </Row>
      )}

      <Card title={`文档列表 (${total})`}>
        <Table
          columns={columns}
          dataSource={docs}
          rowKey="id"
          loading={loading}
          size="small"
          pagination={{ pageSize: 10 }}
        />
      </Card>

      <Modal
        title="录入车辆数据到知识库"
        open={modalOpen}
        onOk={handleIngest}
        onCancel={() => { setModalOpen(false); form.resetFields() }}
        confirmLoading={submitting}
        okText="录入"
        cancelText="取消"
        width={640}
      >
        <Form form={form} layout="vertical">
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="brand" label="品牌" rules={[{ required: true, message: '请输入品牌' }]}>
                <Input placeholder="如: 特斯拉" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="model" label="车型" rules={[{ required: true, message: '请输入车型' }]}>
                <Input placeholder="如: Model 3" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="year" label="年份">
                <Input placeholder="如: 2025" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="price" label="官方售价">
                <Input placeholder="如: 231,900 元" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="dealer_price" label="经销商报价">
                <Input placeholder="如: 229,000 元" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="used_price" label="二手车价格">
                <Input placeholder="如: 180,000 元 (2023款)" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={6}>
              <Form.Item name="energy_type" label="能源类型">
                <Select allowClear placeholder="选择" options={[
                  { value: '纯电动', label: '纯电动' },
                  { value: '增程式', label: '增程式' },
                  { value: '插电混动', label: '插电混动' },
                  { value: '燃油', label: '燃油' },
                  { value: '混动', label: '混动' },
                ]} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="range_km" label="续航">
                <Input placeholder="如: 606 km" />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="horsepower" label="马力">
                <Input placeholder="如: 286 马力" />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="battery" label="电池">
                <Input placeholder="如: 60 kWh" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="source_url" label="来源 URL">
            <Input placeholder="https://..." />
          </Form.Item>
          <Form.Item name="content" label="详细描述">
            <TextArea rows={3} placeholder="车辆的详细描述信息..." />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="上传文档导入知识库"
        open={uploadModalOpen}
        onCancel={() => { setUploadModalOpen(false); setUploadProgress(0) }}
        footer={null}
        destroyOnClose
        width={520}
      >
        <Upload.Dragger
          accept=".txt,.pdf,.md,.json,.csv"
          maxCount={1}
          beforeUpload={handleFileUpload}
          showUploadList={false}
          disabled={uploading}
        >
          <p className="ant-upload-drag-icon">
            <UploadOutlined style={{ fontSize: 36, color: '#1677ff' }} />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此处上传</p>
          <p className="ant-upload-hint">
            支持 .txt / .pdf / .md / .json / .csv 格式，单个文件不超过 20MB
          </p>
        </Upload.Dragger>
        {uploading && (
          <div style={{ marginTop: 16 }}>
            <Progress percent={uploadProgress} status="active" strokeColor="#1677ff" />
          </div>
        )}
      </Modal>
    </div>
  )
}

export default RAGManager
