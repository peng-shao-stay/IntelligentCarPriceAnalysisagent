"""
用户认证相关的 Schema 定义
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserRegisterRequest(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=3, max_length=100, description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=6, max_length=128, description="密码")


class UserLoginRequest(BaseModel):
    """用户登录请求"""
    account: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")
    captcha: Optional[str] = Field(None, description="验证码")
    captcha_id: Optional[str] = Field(None, description="验证码ID")
    remember_me: bool = Field(False, description="是否记住我")


class CaptchaResponse(BaseModel):
    """验证码响应"""
    captcha_id: str = Field(..., description="验证码ID")
    captcha_image: str = Field(..., description="Base64编码的验证码图片")


class LoginResponse(BaseModel):
    """登录响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")
    user_id: Optional[int] = Field(None, description="用户ID")
    username: Optional[str] = Field(None, description="用户名")
    token: Optional[str] = Field(None, description="认证令牌")
    role: Optional[str] = Field(None, description="用户角色")


class TokenVerifyRequest(BaseModel):
    """Token 验证请求"""
    token: str = Field(..., description="JWT token")


class UserInfo(BaseModel):
    """用户信息"""
    id: int
    username: str
    email: Optional[str] = None
    role: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DataListResponse(BaseModel):
    """数据列表响应"""
    total: int
    page: int
    page_size: int
    items: list


class DataItemResponse(BaseModel):
    """废弃：请使用 RAG 文档管理 API 替代。保持向后兼容。"""
    id: int
    brand_name: Optional[str] = None
    model_name: Optional[str] = None
    version_name: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    region: Optional[str] = None
    source: Optional[str] = None
    trend: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DataItemUpdate(BaseModel):
    """废弃：请使用 RAG 文档管理 API 替代。保持向后兼容。"""
    brand_name: Optional[str] = None
    model_name: Optional[str] = None
    version_name: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    region: Optional[str] = None
    source: Optional[str] = None
    trend: Optional[str] = None
