"""
汽车相关的 Pydantic 模型
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class CarPriceBase(BaseModel):
    """汽车价格基础模型"""
    brand: str = Field(..., description="品牌")
    model: str = Field(..., description="车型")
    version: Optional[str] = Field(None, description="版本")
    price: float = Field(..., gt=0, description="价格")
    currency: Optional[str] = Field("CNY", description="货币单位")
    source: Optional[str] = Field(None, description="数据来源")
    region: Optional[str] = Field(None, description="地区")
    url: Optional[str] = Field(None, description="原始链接")


class CarPriceCreate(CarPriceBase):
    """创建汽车价格的请求模型"""
    pass


class CarPriceResponse(CarPriceBase):
    """汽车价格响应模型"""
    id: int
    captured_at: datetime
    
    class Config:
        from_attributes = True


class CarPriceQuery(BaseModel):
    """汽车价格查询模型"""
    brand: Optional[str] = Field(None, description="品牌")
    model: Optional[str] = Field(None, description="车型")
    min_price: Optional[float] = Field(None, ge=0, description="最低价格")
    max_price: Optional[float] = Field(None, ge=0, description="最高价格")
    limit: int = Field(50, ge=1, le=200, description="返回数量限制")
    
    
class CarComparisonRequest(BaseModel):
    """汽车对比请求模型"""
    cars: List[dict] = Field(..., min_length=2, max_length=5, description="要对比的汽车列表")
    # 每辆车应包含 brand, model, version 字段
    
    
class CarComparisonResponse(BaseModel):
    """汽车对比响应模型"""
    comparison_result: str = Field(..., description="对比分析结果")
    cars_compared: List[CarPriceResponse]
    
    
class NewsArticleResponse(BaseModel):
    """新闻文章响应模型"""
    id: int
    title: str
    summary: Optional[str] = None
    source: Optional[str] = None
    url: str
    published_at: Optional[datetime] = None
    captured_at: datetime
    related_brand: Optional[str] = None
    
    class Config:
        from_attributes = True
