"""
MCP (Model Context Protocol) data models.

Defines the request/response structures for JSON-RPC 2.0 based
MCP communication with external tool servers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MCPTransport(str, Enum):
    """Transport protocol for MCP communication."""
    HTTP = "http"
    STDIO = "stdio"
    SSE = "sse"


class MCPAuthType(str, Enum):
    """Authentication types supported for MCP servers."""
    NONE = "none"
    BEARER = "bearer"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"


# ── JSON-RPC 2.0 structures ──────────────────────────────────

@dataclass
class JSONRPCRequest:
    """A JSON-RPC 2.0 request to an MCP server."""
    method: str
    params: Dict[str, Any] = field(default_factory=dict)
    jsonrpc: str = "2.0"
    req_id: int = 1


@dataclass
class JSONRPCResponse:
    """A JSON-RPC 2.0 response from an MCP server."""
    result: Any = None
    error: Optional[JSONRPCError] = None
    jsonrpc: str = "2.0"
    id: Optional[int] = None

    @property
    def success(self) -> bool:
        return self.error is None


@dataclass
class JSONRPCError:
    """JSON-RPC 2.0 error object."""
    code: int
    message: str
    data: Any = None


# ── MCP Tool structures ──────────────────────────────────────

@dataclass
class MCPToolSchema:
    """Schema definition for an MCP tool's input parameters (JSON Schema subset)."""
    type: str = "object"
    properties: Dict[str, Any] = field(default_factory=dict)
    required: List[str] = field(default_factory=list)


@dataclass
class MCPTool:
    """Represents a tool exposed by an MCP server."""
    name: str
    description: str
    input_schema: MCPToolSchema = field(default_factory=MCPToolSchema)
    server_name: str = ""
    server_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": self.input_schema.type,
                "properties": self.input_schema.properties,
                "required": self.input_schema.required,
            },
            "server_name": self.server_name,
            "server_id": self.server_id,
        }


@dataclass
class MCPToolCallResult:
    """Result of calling an MCP tool."""
    tool_name: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    latency_ms: float = 0.0


# ── Server configuration ─────────────────────────────────────

@dataclass
class MCPServerConfig:
    """Configuration for connecting to an MCP server (runtime representation)."""
    name: str
    description: str = ""
    transport: MCPTransport = MCPTransport.HTTP
    base_url: str = ""
    command: str = ""               # for stdio transport
    env_vars: Dict[str, str] = field(default_factory=dict)
    auth_type: MCPAuthType = MCPAuthType.NONE
    auth_config: Dict[str, str] = field(default_factory=dict)
    is_enabled: bool = True
    is_essential: bool = False      # essential servers can't be disabled from frontend
    timeout_seconds: int = 30
    max_retries: int = 2
    config_id: Optional[int] = None

    @classmethod
    def model_validate(cls, row) -> "MCPServerConfig":
        """Convert an ORM model row to a runtime MCPServerConfig."""
        return cls(
            config_id=row.id,
            name=row.name,
            description=row.description or "",
            transport=MCPTransport(row.transport),
            base_url=row.base_url or "",
            command=row.command or "",
            env_vars=row.env_vars or {},
            auth_type=MCPAuthType(row.auth_type),
            auth_config=row.auth_config or {},
            is_enabled=row.is_enabled,
            is_essential=row.is_essential,
            timeout_seconds=row.timeout_seconds,
            max_retries=row.max_retries,
        )
