import React, { useEffect, useState, useCallback } from 'react'
import {
  Table, Input, Select, Button, Space, Tag, Modal,
  Form, InputNumber, message, Popconfirm, Empty, Spin, Card,
  Row, Col,
} from 'antd'
import {
  SearchOutlined, ReloadOutlined, DeleteOutlined,
  EditOutlined, EyeOutlined, ExclamationCircleOutlined,
} from '@ant-design/icons'
import {
  fetchDataList, fetchBrands, getDataItem,
  updateDataItem, deleteDataItem, batchDeleteItems,
} from '../api/data'
import '../styles/DataListPage.css'

const TREND_COLORS = { up: 'green', down: 'red', stable: 'blue' }
const TREND_LABELS = { up: '上涨', down: '下跌', stable: '持平' }
const TREND_OPTIONS = [
  { label: '上涨', value: 'up' },
  { label: '下跌', value: 'down' },
  { label: '持平', value: 'stable' },
]

function formatPrice(val, currency) {
  const symbol = currency === 'USD' ? '$' : '¥'
  return `${symbol}${val != null ? Number(val).toLocaleString() : '-'}`
}

function DataListPage() {
  const [editForm] = Form.useForm()

  // 数据状态
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [total, setTotal] = useState(0)

  // 筛选状态
  const [keyword, setKeyword] = useState('')
  const [brandFilter, setBrandFilter] = useState('')
  const [trendFilter, setTrendFilter] = useState('')
  const [brands, setBrands] = useState([])

  // 分页和排序
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [sortField, setSortField] = useState('created_at')
  const [sortOrder, setSortOrder] = useState('desc')

  // 选择
  const [selectedRowKeys, setSelectedRowKeys] = useState([])

  // 编辑弹窗
  const [editVisible, setEditVisible] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const [editLoading, setEditLoading] = useState(false)

  // 详情弹窗
  const [detailVisible, setDetailVisible] = useState(false)
  const [detailItem, setDetailItem] = useState(null)

  const userInfo = JSON.parse(localStorage.getItem('user_info') || '{}')
  const isAdmin = userInfo.role === 'admin'

  const loadBrands = useCallback(async () => {
    try {
      const list = await fetchBrands()
      setBrands(list)
    } catch {
      // 品牌列表加载失败不影响主列表
    }
  }, [])

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchDataList({
        page, page_size: pageSize, keyword,
        brand: brandFilter, trend: trendFilter,
        sort_field: sortField, sort_order: sortOrder,
      })
      setData(result.items)
      setTotal(result.total)
    } catch (err) {
      setError(err.message || '加载数据失败')
      setData([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, keyword, brandFilter, trendFilter, sortField, sortOrder])

  useEffect(() => {
    loadData()
  }, [loadData])

  useEffect(() => {
    loadBrands()
  }, [])

  const handleSearch = () => {
    setPage(1)
  }

  const handleReset = () => {
    setKeyword('')
    setBrandFilter('')
    setTrendFilter('')
    setPage(1)
  }

  const handleTableChange = (pagination, _filters, sorter) => {
    setPage(pagination.current)
    setPageSize(pagination.pageSize)
    if (sorter.field) {
      setSortField(sorter.field === 'price' ? 'price' : sorter.field)
      setSortOrder(sorter.order === 'ascend' ? 'asc' : 'desc')
    }
  }

  // 批量删除
  const handleBatchDelete = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择要删除的数据')
      return
    }
    try {
      await batchDeleteItems(selectedRowKeys)
      message.success(`成功删除 ${selectedRowKeys.length} 条数据`)
      setSelectedRowKeys([])
      loadData()
    } catch (err) {
      message.error(err.message || '批量删除失败')
    }
  }

  // 单条删除
  const handleDelete = async (id) => {
    try {
      await deleteDataItem(id)
      message.success('删除成功')
      loadData()
    } catch (err) {
      message.error(err.message || '删除失败')
    }
  }

  // 打开编辑弹窗
  const handleEdit = async (record) => {
    try {
      const item = await getDataItem(record.id)
      setEditingItem(item)
      editForm.setFieldsValue(item)
      setEditVisible(true)
    } catch (err) {
      message.error(err.message || '获取数据详情失败')
    }
  }

  // 提交编辑
  const handleEditSubmit = async () => {
    try {
      const values = await editForm.validateFields()
      setEditLoading(true)
      await updateDataItem(editingItem.id, values)
      message.success('更新成功')
      setEditVisible(false)
      loadData()
    } catch (err) {
      if (err.errorFields) return // 表单验证错误
      message.error(err.message || '更新失败')
    } finally {
      setEditLoading(false)
    }
  }

  // 查看详情
  const handleView = async (record) => {
    try {
      const item = await getDataItem(record.id)
      setDetailItem(item)
      setDetailVisible(true)
    } catch (err) {
      message.error(err.message || '获取详情失败')
    }
  }

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      width: 80,
      sorter: true,
      responsive: ['md'],
    },
    {
      title: '品牌',
      dataIndex: 'brand_name',
      width: 120,
      sorter: true,
      ellipsis: true,
    },
    {
      title: '车型',
      dataIndex: 'model_name',
      width: 180,
      ellipsis: true,
    },
    {
      title: '版本',
      dataIndex: 'version_name',
      width: 150,
      ellipsis: true,
      responsive: ['lg'],
    },
    {
      title: '价格',
      dataIndex: 'price',
      width: 130,
      sorter: true,
      render: (val, record) => (
        <span style={{ fontWeight: 600, color: '#1677ff' }}>
          {formatPrice(val, record.currency)}
        </span>
      ),
    },
    {
      title: '地区',
      dataIndex: 'region',
      width: 100,
      responsive: ['md'],
    },
    {
      title: '趋势',
      dataIndex: 'trend',
      width: 90,
      render: (trend) =>
        trend ? <Tag color={TREND_COLORS[trend] || 'default'}>{TREND_LABELS[trend] || trend}</Tag> : '-',
    },
    {
      title: '来源',
      dataIndex: 'source',
      width: 100,
      ellipsis: true,
      responsive: ['lg'],
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      width: 170,
      sorter: true,
      responsive: ['md'],
      render: (val) => val ? new Date(val).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作',
      key: 'actions',
      width: 180,
      fixed: 'right',
      render: (_, record) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleView(record)}
          >
            查看
          </Button>
          {isAdmin && (
            <>
              <Button
                type="link"
                size="small"
                icon={<EditOutlined />}
                onClick={() => handleEdit(record)}
              >
                编辑
              </Button>
              <Popconfirm
                title="确定删除该条数据？"
                onConfirm={() => handleDelete(record.id)}
                okText="确定"
                cancelText="取消"
              >
                <Button
                  type="link"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                >
                  删除
                </Button>
              </Popconfirm>
            </>
          )}
        </Space>
      ),
    },
  ]

  const rowSelection = isAdmin ? {
    selectedRowKeys,
    onChange: setSelectedRowKeys,
    selections: [
      Table.SELECTION_ALL,
      Table.SELECTION_INVERT,
      Table.SELECTION_NONE,
    ],
  } : undefined

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>数据管理</h2>

      {/* 搜索和筛选区域 */}
      <Card style={{ marginBottom: 16 }} size="small">
          <Row gutter={[16, 12]} align="middle">
            <Col xs={24} sm={12} md={6}>
              <Input
                placeholder="搜索品牌、车型、版本..."
                prefix={<SearchOutlined />}
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                onPressEnter={handleSearch}
                allowClear
              />
            </Col>
            <Col xs={12} sm={6} md={4}>
              <Select
                placeholder="品牌筛选"
                value={brandFilter || undefined}
                onChange={(v) => { setBrandFilter(v || ''); setPage(1) }}
                allowClear
                style={{ width: '100%' }}
                options={brands.map((b) => ({ label: b, value: b }))}
              />
            </Col>
            <Col xs={12} sm={6} md={4}>
              <Select
                placeholder="趋势筛选"
                value={trendFilter || undefined}
                onChange={(v) => { setTrendFilter(v || ''); setPage(1) }}
                allowClear
                style={{ width: '100%' }}
                options={TREND_OPTIONS}
              />
            </Col>
            <Col xs={24} sm={12} md={10}>
              <Space wrap>
                <Button
                  type="primary"
                  icon={<SearchOutlined />}
                  onClick={handleSearch}
                >
                  搜索
                </Button>
                <Button icon={<ReloadOutlined />} onClick={handleReset}>
                  重置
                </Button>
                <Button icon={<ReloadOutlined />} onClick={loadData}>
                  刷新
                </Button>
                {isAdmin && selectedRowKeys.length > 0 && (
                  <Popconfirm
                    title={`确定删除选中的 ${selectedRowKeys.length} 条数据？`}
                    onConfirm={handleBatchDelete}
                    okText="确定"
                    cancelText="取消"
                  >
                    <Button danger icon={<DeleteOutlined />}>
                      批量删除 ({selectedRowKeys.length})
                    </Button>
                  </Popconfirm>
                )}
              </Space>
            </Col>
          </Row>
        </Card>

        {/* 错误状态 */}
        {error && (
          <Card className="state-card error-card">
            <div className="state-content">
              <ExclamationCircleOutlined className="state-icon error-icon" />
              <div className="state-text">
                <h3>加载失败</h3>
                <p>{error}</p>
              </div>
              <Button type="primary" onClick={loadData}>
                重试
              </Button>
            </div>
          </Card>
        )}

        {/* 表格 */}

          {/* 加载状态 */}
          {loading && data.length === 0 && !error ? (
            <Card className="state-card">
              <div className="state-content">
                <Spin size="large" />
                <p style={{ marginTop: 16, color: '#999' }}>正在加载数据...</p>
              </div>
            </Card>
          ) : (
            <Card className="table-card" size="small">
              <Table
                rowKey="id"
                columns={columns}
                dataSource={data}
                rowSelection={rowSelection}
                loading={loading && data.length > 0}
                onChange={handleTableChange}
                scroll={{ x: 1200 }}
                locale={{
                  emptyText: (
                    <Empty
                      description={
                        keyword || brandFilter || trendFilter
                          ? '没有匹配的数据，请调整筛选条件'
                          : '暂无数据'
                      }
                    />
                  ),
                }}
                pagination={{
                  current: page,
                  pageSize,
                  total,
                  showSizeChanger: true,
                  showQuickJumper: true,
                  pageSizeOptions: ['10', '20', '50', '100'],
                  showTotal: (t) => `共 ${t} 条数据`,
                  responsive: true,
                }}
              />
            </Card>
          )}

        {/* 编辑弹窗 */}
        <Modal
          title="编辑数据"
          open={editVisible}
          onOk={handleEditSubmit}
          onCancel={() => setEditVisible(false)}
          confirmLoading={editLoading}
          width={600}
          destroyOnClose
        >
          <Form form={editForm} layout="vertical" style={{ marginTop: 16 }}>
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item name="brand_name" label="品牌" rules={[{ required: true, message: '请输入品牌' }]}>
                  <Input />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="model_name" label="车型" rules={[{ required: true, message: '请输入车型' }]}>
                  <Input />
                </Form.Item>
              </Col>
            </Row>
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item name="version_name" label="版本">
                  <Input />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="price" label="价格" rules={[{ required: true, message: '请输入价格' }]}>
                  <InputNumber min={0} style={{ width: '100%' }} precision={2} />
                </Form.Item>
              </Col>
            </Row>
            <Row gutter={16}>
              <Col span={8}>
                <Form.Item name="currency" label="货币">
                  <Select options={[
                    { label: 'CNY (人民币)', value: 'CNY' },
                    { label: 'USD (美元)', value: 'USD' },
                  ]} />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item name="region" label="地区">
                  <Input />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item name="trend" label="趋势">
                  <Select allowClear options={TREND_OPTIONS} />
                </Form.Item>
              </Col>
            </Row>
            <Form.Item name="source" label="来源">
              <Input />
            </Form.Item>
          </Form>
        </Modal>

        {/* 详情弹窗 */}
        <Modal
          title="数据详情"
          open={detailVisible}
          onCancel={() => setDetailVisible(false)}
          footer={<Button onClick={() => setDetailVisible(false)}>关闭</Button>}
          width={560}
        >
          {detailItem && (
            <div className="detail-grid">
              {[
                ['品牌', detailItem.brand_name],
                ['车型', detailItem.model_name],
                ['版本', detailItem.version_name],
                ['价格', formatPrice(detailItem.price, detailItem.currency)],
                ['货币', detailItem.currency],
                ['地区', detailItem.region],
                ['趋势', detailItem.trend],
                ['来源', detailItem.source],
                ['创建时间', detailItem.created_at ? new Date(detailItem.created_at).toLocaleString('zh-CN') : '-'],
                ['更新时间', detailItem.updated_at ? new Date(detailItem.updated_at).toLocaleString('zh-CN') : '-'],
              ].map(([label, value]) => (
                <div key={label} className="detail-row">
                  <span className="detail-label">{label}</span>
                  <span className="detail-value">{value || '-'}</span>
                </div>
              ))}
            </div>
          )}
        </Modal>
    </div>
  )
}

export default DataListPage
