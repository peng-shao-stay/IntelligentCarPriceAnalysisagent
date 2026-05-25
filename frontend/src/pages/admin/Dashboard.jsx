import React, { useEffect, useState } from 'react'
import { Row, Col, Card, Statistic, Table, Spin, Empty, Select, Tag } from 'antd'
import {
  UserOutlined, CommentOutlined, DatabaseOutlined,
  RiseOutlined, TeamOutlined, FileTextOutlined,
  SettingOutlined, PlusCircleOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { useNavigate } from 'react-router-dom'
import { fetchDashboardStats, fetchMessageTrend, fetchRecentActivity } from '../../api/admin'
import { useTheme } from '../../context/ThemeContext'

const quickActions = [
  { icon: <TeamOutlined />, label: '用户管理', path: '/admin/users', color: '#1677ff' },
  { icon: <DatabaseOutlined />, label: '数据管理', path: '/admin/data', color: '#52c41a' },
  { icon: <SettingOutlined />, label: '系统设置', path: '#', color: '#fa8c16' },
  { icon: <PlusCircleOutlined />, label: '添加用户', path: '/admin/users', color: '#722ed1' },
]

function Dashboard() {
  const navigate = useNavigate()
  const { dark } = useTheme()
  const [stats, setStats] = useState(null)
  const [trend, setTrend] = useState([])
  const [activity, setActivity] = useState([])
  const [loading, setLoading] = useState(true)
  const [trendDays, setTrendDays] = useState(7)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const [s, t, a] = await Promise.all([
          fetchDashboardStats(),
          fetchMessageTrend(trendDays),
          fetchRecentActivity(10),
        ])
        setStats(s)
        setTrend(t)
        setActivity(a)
      } catch { /* 静默处理 */ } finally {
        setLoading(false)
      }
    }
    load()
  }, [trendDays])

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>

  const textColor = dark ? '#e0e0e0' : '#333'
  const cardBg = dark ? '#1f1f1f' : '#fff'

  const lineOption = {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: trend.map((t) => t.date), axisLabel: { color: textColor } },
    yAxis: { type: 'value', axisLabel: { color: textColor } },
    series: [{
      data: trend.map((t) => t.count), type: 'line', smooth: true,
      areaStyle: { color: 'rgba(22,119,255,0.15)' },
      itemStyle: { color: '#1677ff' },
    }],
    grid: { left: 40, right: 20, top: 20, bottom: 30 },
  }

  const pieOption = {
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie', radius: ['40%', '70%'],
      data: [
        { value: stats?.total_users || 0, name: '用户' },
        { value: stats?.total_sessions || 0, name: '会话' },
        { value: stats?.total_messages || 0, name: '消息' },
        { value: stats?.total_data || 0, name: '数据' },
      ],
      label: { color: textColor },
    }],
  }

  const activityColumns = [
    { title: '会话ID', dataIndex: 'session_id', ellipsis: true, width: 160 },
    { title: '标题', dataIndex: 'title', ellipsis: true },
    { title: '更新时间', dataIndex: 'updated_at', width: 170, render: (v) => v ? new Date(v).toLocaleString('zh-CN') : '-' },
  ]

  return (
    <div style={{ color: textColor }}>
      <h2 style={{ marginBottom: 24 }}>仪表盘</h2>

      {/* 统计卡片 */}
      <Row gutter={[16, 16]}>
        {[
          { title: '总用户数', value: stats?.total_users, icon: <UserOutlined />, color: '#1677ff' },
          { title: '总会话数', value: stats?.total_sessions, icon: <CommentOutlined />, color: '#52c41a' },
          { title: '总消息数', value: stats?.total_messages, icon: <FileTextOutlined />, color: '#fa8c16' },
          { title: '今日新增用户', value: stats?.new_users_today, icon: <RiseOutlined />, color: '#722ed1' },
        ].map(({ title, value, icon, color }) => (
          <Col xs={24} sm={12} lg={6} key={title}>
            <Card style={{ background: cardBg }}>
              <Statistic
                title={title}
                value={value ?? '-'}
                prefix={<span style={{ color, fontSize: 24 }}>{icon}</span>}
              />
            </Card>
          </Col>
        ))}
      </Row>

      {/* 图表 + 最近活动 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={14}>
          <Card title="消息趋势" style={{ background: cardBg }} extra={
            <Select value={trendDays} onChange={setTrendDays} size="small" style={{ width: 100 }}
              options={[{ label: '近7天', value: 7 }, { label: '近30天', value: 30 }, { label: '近90天', value: 90 }]}
            />
          }>
            {trend.length > 0 ? (
              <ReactECharts option={lineOption} style={{ height: 320 }} />
            ) : (
              <Empty description="暂无趋势数据" />
            )}
          </Card>
        </Col>

        <Col xs={24} lg={10}>
          <Card title="数据概览" style={{ background: cardBg }}>
            {stats ? (
              <ReactECharts option={pieOption} style={{ height: 320 }} />
            ) : (
              <Empty description="暂无数据" />
            )}
          </Card>
        </Col>
      </Row>

      {/* 快捷操作 + 最近活动 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={8}>
          <Card title="快捷操作" style={{ background: cardBg }}>
            <Row gutter={[12, 12]}>
              {quickActions.map(({ icon, label, path, color }) => (
                <Col span={12} key={label}>
                  <Card
                    hoverable
                    size="small"
                    onClick={() => path !== '#' && navigate(path)}
                    style={{ textAlign: 'center', cursor: 'pointer' }}
                  >
                    <div style={{ fontSize: 28, color }}>{icon}</div>
                    <div style={{ marginTop: 8, fontSize: 13 }}>{label}</div>
                  </Card>
                </Col>
              ))}
            </Row>
          </Card>
        </Col>

        <Col xs={24} md={16}>
          <Card title="最近活动" style={{ background: cardBg }}>
            {activity.length > 0 ? (
              <Table
                dataSource={activity}
                columns={activityColumns}
                rowKey="session_id"
                size="small"
                pagination={false}
                scroll={{ x: 400 }}
              />
            ) : (
              <Empty description="暂无活动" />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default Dashboard
