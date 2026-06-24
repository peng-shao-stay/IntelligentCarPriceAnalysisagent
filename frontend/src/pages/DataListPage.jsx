import React, { useEffect, useState, useCallback, useRef } from 'react'
import {
  Table, Input, Select, Button, Space, Tag, Modal,
  Form, message, Popconfirm, Empty, Spin, Card,
  Row, Col, Typography,
} from 'antd'
import {
  SearchOutlined, ReloadOutlined, DeleteOutlined,
  EditOutlined, EyeOutlined, ExclamationCircleOutlined,
} from '@ant-design/icons'
import {
  fetchDataList, fetchBrands, fetchChunkTypes,
  getDataItem, updateDataItem, deleteDataItem, batchDeleteItems,
} from '../api/data'
import '../styles/DataListPage.css'

const CHUNK_TYPE_LABELS = {
  brand: '品牌概述', model: '车型', feature: '特性', comparison: '对比',
}
const CHUNK_TYPE_COLORS = {
  brand: 'purple', model: 'blue', feature: 'green', comparison: 'orange',
}

function formatPriceRange(val) {
  return val || '-'
}

function DataListPage() {
  const [editForm] = Form.useForm()

  // 数据状态
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [total, setTotal] = useState(0)

  // 筛选状态
  const [keyword, setKeyword] = useState('')              // 输入框即时显示
  const [searchKeyword, setSearchKeyword] = useState('')  // 实际搜索关键词（防抖后）
  const [brandFilter, setBrandFilter] = useState('')
  const [chunkTypeFilter, setChunkTypeFilter] = useState('')
  const [brands, setBrands] = useState([])
  const [chunkTypes, setChunkTypes] = useState([])

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

  // 并行加载筛选下拉选项（挂载时）
  useEffect(() => {
    Promise.all([
      fetchBrands().catch(() => []),
      fetchChunkTypes().catch(() => []),
    ]).then(([brandsList, typesList]) => {
      setBrands(brandsList)
      setChunkTypes(typesList)
    })
  }, [])

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchDataList({
        page, page_size: pageSize, keyword: searchKeyword,
        brand: brandFilter, chunk_type: chunkTypeFilter,
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
  }, [page, pageSize, searchKeyword, brandFilter, chunkTypeFilter, sortField, sortOrder])

  // 关键词输入防抖（300ms 后自动搜索）
  const debounceRef = useRef(null)
  const handleKeywordChange = useCallback((value) => {
    setKeyword(value)
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setSearchKeyword(value)
      setPage(1)
    }, 300)
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  // 组件卸载时清除防抖定时器
  useEffect(() => {
    return () => clearTimeout(debounceRef.current)
  }, [])

  const handleSearch = () => {
    setSearchKeyword(keyword)
    setPage(1)
  }

  const handleReset = () => {
    setKeyword('')
    setSearchKeyword('')
    setBrandFilter('')
    setChunkTypeFilter('')
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
      width: 70,
      sorter: true,
      responsive: ['md'],
    },
    {
      title: '品牌',
      dataIndex: 'brand_name',
      width: 100,
      ellipsis: true,
    },
    {
      title: '车型',
      dataIndex: 'model_name',
      width: 150,
      ellipsis: true,
    },
    {
      title: '区块类型',
      dataIndex: 'chunk_type',
      width: 100,
      render: (t) => t ? <Tag color={CHUNK_TYPE_COLORS[t] || 'default'}>{CHUNK_TYPE_LABELS[t] || t}</Tag> : '-',
    },
    {
      title: '区块标识',
      dataIndex: 'chunk_id',
      width: 220,
      ellipsis: true,
      responsive: ['lg'],
    },
    {
      title: '价格区间',
      dataIndex: 'price_range',
      width: 120,
      render: (val) => (
        <span style={{ fontWeight: 600, color: '#1677ff' }}>
          {formatPriceRange(val)}
        </span>
      ),
    },
    {
      title: '年份',
      dataIndex: 'year',
      width: 80,
      responsive: ['md'],
    },
    {
      title: '智驾等级',
      dataIndex: 'smart_drive',
      width: 90,
      render: (val) => val ? <Tag color="geekblue">{val}</Tag> : '-',
    },
    {
      title: '来源',
      dataIndex: 'source',
      width: 90,
      ellipsis: true,
      responsive: ['lg'],
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      width: 160,
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
                onChange={(e) => handleKeywordChange(e.target.value)}
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
                placeholder="区块类型筛选"
                value={chunkTypeFilter || undefined}
                onChange={(v) => { setChunkTypeFilter(v || ''); setPage(1) }}
                allowClear
                style={{ width: '100%' }}
                options={chunkTypes.map((t) => ({ label: CHUNK_TYPE_LABELS[t] || t, value: t }))}
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
                        keyword || brandFilter || chunkTypeFilter
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
          title="编辑区块数据"
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
              <Col span={8}>
                <Form.Item name="chunk_type" label="区块类型">
                  <Select options={Object.entries(CHUNK_TYPE_LABELS).map(([v, l]) => ({ label: l, value: v }))} />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item name="price_range" label="价格区间">
                  <Input placeholder="如 23-34万" />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item name="year" label="年份">
                  <Input placeholder="如 2024" />
                </Form.Item>
              </Col>
            </Row>
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item name="vehicle_type" label="车辆类型">
                  <Input placeholder="如 SUV、轿车" />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="source" label="来源">
                  <Input />
                </Form.Item>
              </Col>
            </Row>
          </Form>
        </Modal>

        {/* 详情弹窗 */}
        <Modal
          title="区块详情"
          open={detailVisible}
          onCancel={() => setDetailVisible(false)}
          footer={<Button onClick={() => setDetailVisible(false)}>关闭</Button>}
          width={640}
        >
          {detailItem && (
            <div className="detail-grid">
              {[
                ['区块ID', detailItem.id],
                ['品牌', detailItem.brand_name],
                ['车型', detailItem.model_name],
                ['区块类型', detailItem.chunk_type ? (CHUNK_TYPE_LABELS[detailItem.chunk_type] || detailItem.chunk_type) : '-'],
                ['区块标识', detailItem.chunk_id],
                ['区块序号', detailItem.chunk_index],
                ['价格区间', detailItem.price_range],
                ['年份', detailItem.year],
                ['车辆类型', detailItem.vehicle_type],
                ['动力类型', Array.isArray(detailItem.power_type) ? detailItem.power_type.join('、') : detailItem.power_type],
                ['智驾等级', detailItem.smart_drive],
                ['来源', detailItem.source],
                ['Token数', detailItem.token_count],
                ['内容摘要', detailItem.content],
                ['创建时间', detailItem.created_at ? new Date(detailItem.created_at).toLocaleString('zh-CN') : '-'],
                ['更新时间', detailItem.updated_at ? new Date(detailItem.updated_at).toLocaleString('zh-CN') : '-'],
              ].filter(([, v]) => v != null && v !== '').map(([label, value]) => (
                <div key={label} className="detail-row">
                  <span className="detail-label">{label}</span>
                  <span className="detail-value" style={label === '内容摘要' ? { maxHeight: 120, overflow: 'auto', whiteSpace: 'pre-wrap' } : {}}>
                    {typeof value === 'string' ? value : String(value)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Modal>
    </div>
  )
}

export default DataListPage
