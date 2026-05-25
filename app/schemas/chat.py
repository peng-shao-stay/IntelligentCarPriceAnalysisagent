"""
聊天相关的 Pydantic 模型
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class MessageCreate(BaseModel):
    """创建消息的请求模型"""
    content: str = Field(..., min_length=1, description="消息内容")
    
    
class MessageResponse(BaseModel):
    """消息响应模型"""
    id: int
    session_id: str
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionCreate(BaseModel):
    """创建会话的请求模型"""
    title: Optional[str] = Field(None, description="会话标题")
    
    
class ChatSessionResponse(BaseModel):
    """会话响应模型"""
    id: int
    session_id: str
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    """聊天请求模型"""
    message: str = Field(..., min_length=1, description="用户消息")
    session_id: Optional[str] = Field(None, description="会话ID,不提供则创建新会话")
    web_search: bool = Field(False, description="是否启用联网搜索")
    
    
class ChatResponse(BaseModel):
    """聊天响应模型"""
    session_id: str
    user_message: MessageResponse
    assistant_message: MessageResponse
    
    
class ChatHistoryResponse(BaseModel):
    """聊天历史响应模型"""
    session: ChatSessionResponse
    messages: List[MessageResponse]


class SaveToKnowledgeBaseRequest(BaseModel):
    """保存内容到知识库的请求模型"""
    content: str = Field(..., min_length=1, description="要保存的内容")
    title: Optional[str] = Field(None, description="内容标题，不提供则自动生成")
    brand: Optional[str] = Field(None, description="关联品牌")
    model: Optional[str] = Field(None, description="关联车型")


class SaveToKnowledgeBaseResponse(BaseModel):
    """保存到知识库的响应模型"""
    success: bool
    document_id: Optional[int] = None
    title: Optional[str] = None
    chunk_count: int = 0
    message: str
