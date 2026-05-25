"""
MCP server management — Pydantic schemas.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MCPServerCreate(BaseModel):
    """Create a new MCP server configuration."""
    name: str = Field(..., min_length=1, max_length=100, description="Unique server name")
    description: str = Field("", max_length=500)
    transport: str = Field("http", pattern="^(http|stdio|sse)$")
    base_url: str = Field("", max_length=500, description="Base URL for HTTP/SSE transport")
    command: str = Field("", max_length=500, description="Command for stdio transport")
    env_vars: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    auth_type: str = Field("none", pattern="^(none|bearer|api_key|oauth2)$")
    auth_config: Dict[str, str] = Field(default_factory=dict, description="Auth credentials")
    is_enabled: bool = True
    is_essential: bool = False
    timeout_seconds: int = Field(30, ge=5, le=300)
    max_retries: int = Field(2, ge=0, le=5)


class MCPServerUpdate(BaseModel):
    """Update an existing MCP server configuration."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    transport: Optional[str] = Field(None, pattern="^(http|stdio|sse)$")
    base_url: Optional[str] = Field(None, max_length=500)
    command: Optional[str] = Field(None, max_length=500)
    env_vars: Optional[Dict[str, str]] = None
    auth_type: Optional[str] = Field(None, pattern="^(none|bearer|api_key|oauth2)$")
    auth_config: Optional[Dict[str, str]] = None
    is_enabled: Optional[bool] = None
    is_essential: Optional[bool] = None
    timeout_seconds: Optional[int] = Field(None, ge=5, le=300)
    max_retries: Optional[int] = Field(None, ge=0, le=5)


class MCPServerResponse(BaseModel):
    """MCP server configuration response."""
    id: int
    name: str
    description: str
    transport: str
    base_url: str
    command: str
    auth_type: str
    # auth_config is masked — never returned to frontend
    tool_schemas: List[Dict[str, Any]] = []
    is_enabled: bool
    is_essential: bool
    timeout_seconds: int
    max_retries: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MCPTestResult(BaseModel):
    """Result of testing an MCP server connection."""
    success: bool
    message: str
    tools_found: int = 0
    tool_names: List[str] = []
    latency_ms: float = 0.0


class MCPToolResponse(BaseModel):
    """MCP tool definition returned to frontend."""
    name: str
    description: str
    input_schema: Dict[str, Any] = {}
    server_name: str
    server_id: Optional[int] = None


class MCPToolsListResponse(BaseModel):
    """List of tools from an MCP server."""
    server_name: str
    tools: List[MCPToolResponse]
    count: int
