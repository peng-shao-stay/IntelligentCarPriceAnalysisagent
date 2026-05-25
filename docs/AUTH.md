# 用户认证系统使用指南

## 📋 功能概述

本次更新为 AutoMind AI 添加了完整的用户认证系统，包括：

✅ **用户注册** - 支持用户名、邮箱和密码注册  
✅ **用户登录** - 支持用户名或邮箱登录  
✅ **验证码** - 图形验证码防止机器人攻击  
✅ **记住我** - 勾选后自动保存登录状态  
✅ **会话持久化** - 刷新页面不会丢失登录状态  
✅ **认证守卫** - 未登录用户自动重定向到登录页  
✅ **退出登录** - 安全退出并清除认证信息  

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd D:\PythonProject\peng-shao-stay-IntelligentCarPriceAnalysisagent

# 安装后端依赖（包含 Pillow）
pip install -r requirements.txt

# 安装前端依赖
cd frontend
npm install
```

### 2. 启动后端服务

```bash
# 在项目根目录
python main.py
```

后端将运行在 `http://localhost:8000`

### 3. 启动前端服务

```bash
# 在 frontend 目录
npm run dev
```

前端将运行在 `http://localhost:3000`

---

## 🔐 使用流程

### 首次访问

1. 打开浏览器访问 `http://localhost:3000`
2. 自动跳转到登录页面

### 注册用户

1. 点击"注册"标签
2. 填写以下信息：
   - 用户名（至少3个字符）
   - 邮箱（有效格式）
   - 密码（至少6个字符）
   - 确认密码
3. 点击"注册"按钮
4. 注册成功后自动切换到登录页面

### 登录系统

1. 在"登录"标签页
2. 输入用户名或邮箱
3. 输入密码
4. 输入右侧显示的4位数字验证码
5. （可选）勾选"记住我"
6. 点击"登录"按钮

### 使用聊天功能

- 登录成功后自动跳转到聊天页面
- 右上角显示当前用户名
- 点击用户名可选择"退出登录"

### 退出登录

1. 点击右上角的用户头像/用户名
2. 选择"退出登录"
3. 自动返回登录页面

---

## 💾 "记住我"功能说明

### 工作原理

- **勾选"记住我"**：
  - 登录信息保存在 `localStorage`
  - 关闭浏览器后再打开，自动保持登录状态
  - 下次访问时自动填充用户名

- **不勾选"记住我"**：
  - 仅在当前会话中保持登录
  - 关闭浏览器后需要重新登录

### 数据存储

认证信息存储在浏览器的 `localStorage` 中：
- `auth_token` - 认证令牌
- `user_info` - 用户信息（JSON格式）
- `remember_me` - 是否记住登录状态

---

## 🛡️ 安全特性

### 1. 密码加密
- 使用 SHA-256 + Salt 进行哈希加密
- 原始密码永不存储

### 2. 验证码保护
- 4位随机数字验证码
- 每次请求自动刷新
- 防止暴力破解和机器人攻击

### 3. 路由保护
- 未登录用户无法访问聊天页面
- 自动重定向到登录页

### 4. 会话管理
- Token 验证机制
- 安全的登出流程

---

## 📁 新增文件清单

### 后端文件
```
app/
├── api/
│   └── auth.py              # 认证 API 路由
├── schemas/
│   └── auth.py              # 认证相关的 Schema
```

### 前端文件
```
frontend/src/
├── api/
│   └── auth.js              # 认证 API 调用
├── components/
│   └── AuthGuard.jsx        # 认证守卫组件
├── pages/
│   └── LoginPage.jsx        # 登录页面（已更新）
└── App.jsx                  # 路由配置（已更新）
```

---

## 🔧 API 接口

### 1. 获取验证码
```
GET /api/v1/auth/captcha

Response:
{
  "captcha_id": "uuid",
  "captcha_image": "data:image/png;base64,..."
}
```

### 2. 用户注册
```
POST /api/v1/auth/register

Request:
{
  "username": "testuser",
  "email": "test@example.com",
  "password": "123456"
}

Response:
{
  "success": true,
  "message": "注册成功",
  "user_id": 1,
  "username": "testuser"
}
```

### 3. 用户登录
```
POST /api/v1/auth/login

Request:
{
  "account": "testuser",  // 用户名或邮箱
  "password": "123456",
  "captcha": "1234",      // 可选
  "remember_me": true     // 可选
}

Response:
{
  "success": true,
  "message": "登录成功",
  "user_id": 1,
  "username": "testuser",
  "token": "random-token-string"
}
```

### 4. 验证令牌
```
GET /api/v1/auth/verify-token?token=xxx

Response:
{
  "valid": true,
  "message": "令牌有效"
}
```

---

## ⚠️ 注意事项

### 生产环境建议

1. **使用 JWT Token**
   - 当前使用简单 token，生产环境应改用 JWT
   - 添加 token 过期时间

2. **HTTPS 加密**
   - 所有认证请求应通过 HTTPS

3. **Redis 存储验证码**
   - 当前使用内存存储，重启后丢失
   - 生产环境应使用 Redis

4. **密码强度要求**
   - 增加密码复杂度要求
   - 包含大小写字母、数字、特殊字符

5. **防止暴力破解**
   - 添加登录失败次数限制
   - IP 封禁机制

6. **邮箱验证**
   - 注册后发送验证邮件
   - 验证通过后激活账户

7. **找回密码功能**
   - 通过邮箱重置密码
   - 安全问题验证

---

## 🐛 常见问题

### Q1: 验证码图片不显示？
**A:** 确保已安装 Pillow 库：
```bash
pip install Pillow
```

### Q2: 登录后刷新页面又要重新登录？
**A:** 检查是否勾选了"记住我"选项。如果已勾选但仍失效，检查浏览器控制台是否有错误。

### Q3: 注册时提示"用户名已存在"？
**A:** 尝试使用其他用户名，或联系管理员删除重复账户。

### Q4: 无法访问聊天页面？
**A:** 确保已成功登录。未登录用户会被自动重定向到登录页。

### Q5: 退出登录后仍能看到聊天内容？
**A:** 这是正常的，退出登录只是清除了认证信息。如需完全清除数据，需要清除浏览器缓存。

---

## 📞 技术支持

如有问题，请检查：
1. 后端日志：`logs/app_YYYY-MM-DD.log`
2. 浏览器控制台错误信息
3. 网络连接是否正常

---

## 🎯 下一步优化计划

- [ ] 实现 JWT Token 认证
- [ ] 添加邮箱验证功能
- [ ] 实现找回密码功能
- [ ] 添加 OAuth2 第三方登录（微信、GitHub）
- [ ] 用户个人资料编辑
- [ ] 头像上传功能
- [ ] 多设备登录管理
- [ ] 登录历史记录
