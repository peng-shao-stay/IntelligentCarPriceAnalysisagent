import React, { useState, useEffect } from 'react'
import {
  Tabs, Form, Input, Button, Checkbox, Divider, message,
} from 'antd'
import {
  UserOutlined, LockOutlined, MailOutlined,
  WechatOutlined, GithubOutlined, SafetyOutlined, ReloadOutlined,
} from '@ant-design/icons'
import { login, register, getCaptcha } from '../api/auth'
import { useNavigate } from 'react-router-dom'
import useChatStore from '../stores/useChatStore'
import '../styles/LoginPage.css'

const loginFields = [
  { name: 'account', label: '用户名 / 邮箱', icon: <UserOutlined />, rules: [{ required: true, message: '请输入用户名或邮箱' }] },
  { name: 'password', label: '密码', icon: <LockOutlined />, type: 'password', rules: [{ required: true, message: '请输入密码' }] },
]

const registerFields = [
  { name: 'username', label: '用户名', icon: <UserOutlined />, rules: [{ required: true, message: '请输入用户名' }, { min: 3, message: '用户名至少3个字符' }] },
  { name: 'email', label: '邮箱', icon: <MailOutlined />, rules: [
    { required: true, message: '请输入邮箱' },
    { type: 'email', message: '邮箱格式不正确' },
  ]},
  { name: 'password', label: '密码', icon: <LockOutlined />, type: 'password', rules: [{ required: true, message: '请输入密码' }, { min: 6, message: '密码至少6个字符' }] },
  { name: 'confirm', label: '确认密码', icon: <LockOutlined />, type: 'password', rules: [
    { required: true, message: '请确认密码' },
    ({ getFieldValue }) => ({
      validator(_, value) {
        if (!value || getFieldValue('password') === value) return Promise.resolve()
        return Promise.reject(new Error('两次输入的密码不一致'))
      },
    }),
  ]},
]

function saveAuthAndRedirect(response, remember, navigate) {
  localStorage.setItem('auth_token', response.token)
  localStorage.setItem('user_info', JSON.stringify({
    user_id: response.user_id,
    username: response.username,
    role: response.role || 'user',
  }))
  if (remember) {
    localStorage.setItem('remember_me', 'true')
  } else {
    localStorage.removeItem('remember_me')
  }
  setTimeout(() => navigate('/chat'), 500)
}

function LoginPage() {
  const navigate = useNavigate()
  const resetStore = useChatStore((s) => s.resetStore)
  const [loginForm] = Form.useForm()
  const [registerForm] = Form.useForm()
  const [loginLoading, setLoginLoading] = useState(false)
  const [registerLoading, setRegisterLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('login')

  const [captchaId, setCaptchaId] = useState('')
  const [captchaImage, setCaptchaImage] = useState('')
  const [captchaLoading, setCaptchaLoading] = useState(false)

  useEffect(() => {
    resetStore()
    if (checkRememberedLogin()) return
    fetchCaptcha()
  }, [])

  const fetchCaptcha = async () => {
    try {
      setCaptchaLoading(true)
      const response = await getCaptcha()
      setCaptchaId(response.captcha_id)
      setCaptchaImage(response.captcha_image)
    } catch {
      message.error('获取验证码失败')
    } finally {
      setCaptchaLoading(false)
    }
  }

  const checkRememberedLogin = () => {
    const remembered = localStorage.getItem('remember_me')
    const userInfo = localStorage.getItem('user_info')
    const token = localStorage.getItem('auth_token')

    if (remembered === 'true' && userInfo && token) {
      const user = JSON.parse(userInfo)
      loginForm.setFieldsValue({ account: user.username, remember: true })
      navigate('/chat')
      return true
    }
    return false
  }

  const handleLogin = async (values) => {
    setLoginLoading(true)
    try {
      const response = await login({
        account: values.account,
        password: values.password,
        captcha: values.captcha,
        captcha_id: captchaId,
        remember_me: values.remember || false,
      })

      if (response.success) {
        message.success('登录成功！')
        saveAuthAndRedirect(response, values.remember, navigate)
      } else {
        message.error(response.message || '登录失败')
      }
    } catch (error) {
      message.error(error.message || '登录失败，请检查网络连接')
      fetchCaptcha()
      loginForm.setFieldsValue({ captcha: '' })
    } finally {
      setLoginLoading(false)
    }
  }

  const handleRegister = async (values) => {
    setRegisterLoading(true)
    try {
      const response = await register({
        username: values.username,
        email: values.email,
        password: values.password,
      })

      if (response.success) {
        message.success('注册成功！')
        saveAuthAndRedirect(response, false, navigate)
        registerForm.resetFields()
      } else {
        message.error(response.message || '注册失败')
      }
    } catch (error) {
      message.error(error.message || '注册失败，请检查网络连接')
    } finally {
      setRegisterLoading(false)
    }
  }

  const renderLoginForm = (form, loading) => (
    <Form form={form} onFinish={handleLogin} layout="vertical" size="large" autoComplete="off">
      {loginFields.map((f) => (
        <Form.Item key={f.name} name={f.name} rules={f.rules}>
          <Input prefix={f.icon} type={f.type || 'text'} placeholder={f.label} className="login-field" />
        </Form.Item>
      ))}

      <Form.Item name="captcha" rules={[{ required: true, message: '请输入验证码' }]}>
        <div style={{ display: 'flex', gap: '8px' }}>
          <Input prefix={<SafetyOutlined />} placeholder="验证码" className="login-field" style={{ flex: 1 }} />
          <div
            onClick={fetchCaptcha}
            style={{
              cursor: 'pointer', border: '1px solid #d9d9d9', borderRadius: '4px',
              overflow: 'hidden', width: '120px', height: '40px',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: '#f5f5f5',
            }}
            title="点击刷新验证码"
          >
            {captchaLoading ? <ReloadOutlined spin /> : captchaImage ? <img src={captchaImage} alt="验证码" style={{ width: '100%', height: '100%' }} /> : <ReloadOutlined />}
          </div>
        </div>
      </Form.Item>

      <Form.Item>
        <Button type="primary" htmlType="submit" block loading={loading} className="login-submit">
          {loading ? '处理中...' : '登 录'}
        </Button>
      </Form.Item>

      <div className="login-extra">
        <Form.Item name="remember" valuePropName="checked" noStyle>
          <Checkbox>记住我</Checkbox>
        </Form.Item>
        <a href="#" className="forgot-link" onClick={(e) => e.preventDefault()}>忘记密码？</a>
      </div>
    </Form>
  )

  const renderRegisterForm = (form, loading) => (
    <Form form={form} onFinish={handleRegister} layout="vertical" size="large" autoComplete="off">
      {registerFields.map((f) => (
        <Form.Item key={f.name} name={f.name} rules={f.rules}>
          <Input prefix={f.icon} type={f.type || 'text'} placeholder={f.label} className="login-field" />
        </Form.Item>
      ))}
      <Form.Item>
        <Button type="primary" htmlType="submit" block loading={loading} className="login-submit">
          {loading ? '处理中...' : '注 册'}
        </Button>
      </Form.Item>
    </Form>
  )

  return (
    <div className="login-page">
      <div className="login-container">
        <div className="login-brand">
          <div className="brand-icon">🚗</div>
          <h1 className="brand-title">AutoMind</h1>
          <p className="brand-subtitle">智能汽车价格分析助手</p>
        </div>

        <div className="login-card">
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            centered
            size="large"
            items={[
              { key: 'login', label: <span className="tab-label">登录</span>, children: renderLoginForm(loginForm, loginLoading) },
              { key: 'register', label: <span className="tab-label">注册</span>, children: renderRegisterForm(registerForm, registerLoading) },
            ]}
          />

          <Divider plain className="social-divider">
            <span className="divider-text">其他方式</span>
          </Divider>

          <div className="social-buttons">
            <Button icon={<WechatOutlined />} block className="social-btn wechat-btn">微信登录</Button>
            <Button icon={<GithubOutlined />} block className="social-btn github-btn">GitHub 登录</Button>
          </div>
        </div>

        <p className="login-footer">
          使用即代表同意 <a href="#" onClick={(e) => e.preventDefault()}>服务条款</a> 和 <a href="#" onClick={(e) => e.preventDefault()}>隐私政策</a>
        </p>
      </div>
    </div>
  )
}

export default LoginPage
