"""
MCP (Model Context Protocol) integration layer.

Phase 2: Unified MCP Client with tool discovery, async invocation,
timeout handling, and database-persisted server configurations.

Architecture:
  Agent / Provider Layer
       │
       ▼
  MCPClientFactory
       │
       ├── MCPClient("car-data")    ── HTTP ── Car Data MCP Server
       ├── MCPClient("rag-vector")  ── HTTP ── RAG Vector MCP Server
       └── MCPClient("...")         ── HTTP ── Custom MCP Server

Usage:
  from app.mcp.client import MCPClientFactory, MCPClient
  from app.mcp.models import MCPServerConfig

  config = MCPServerConfig(name="car-data", base_url="http://localhost:9000")
  client = MCPClient(config)
  tools = await client.list_tools()
  result = await client.call_tool("search_car", {"brand": "Tesla"})
"""

from app.mcp.client import MCPClient, MCPClientFactory, mcp_client_factory
from app.mcp.models import (
    MCPAuthType,
    MCPServerConfig,
    MCPTool,
    MCPToolCallResult,
    MCPToolSchema,
    MCPTransport,
)

__all__ = [
    "MCPClient",
    "MCPClientFactory",
    "mcp_client_factory",
    "MCPServerConfig",
    "MCPTool",
    "MCPToolCallResult",
    "MCPToolSchema",
    "MCPTransport",
    "MCPAuthType",
]
