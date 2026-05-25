"""
MCP Servers — independently deployable tool servers for the AutoMind agent.

Each server can run as a standalone process:

  Search MCP Server:    python -m mcp_servers.search_server --port 9100
  Car Data MCP Server:  python -m mcp_servers.car_data_server --port 9101
  RAG Vector MCP Server: python -m mcp_servers.rag_server --port 9102

Or run all three together:
  python -m mcp_servers.run_all

Phase 4: Independent MCP servers with JSON-RPC, JSON Schema, auth, and logging.
"""

from mcp_servers.base import BaseMCPServer, MCPLogger, MCPToolDef

__all__ = [
    "BaseMCPServer",
    "MCPLogger",
    "MCPToolDef",
]
