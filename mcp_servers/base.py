"""
Base MCP Server — FastAPI-based JSON-RPC 2.0 server framework.

Each MCP server:
  - Runs as an independent uvicorn process
  - Exposes a single POST / endpoint for JSON-RPC
  - Supports tools/list and tools/call
  - Has API key authentication
  - Structured JSON logging
  - JSON Schema for all tool inputs

Usage:
  from mcp_servers.base import BaseMCPServer, MCPToolDef

  server = BaseMCPServer(name="my-server", port=9100)
  server.register_tool(MCPToolDef(name="my_tool", ...))
  server.run()
"""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


# ═══════════════════════════════════════════════════════════════
#  Tool Definition
# ═══════════════════════════════════════════════════════════════

@dataclass
class MCPToolDef:
    """Definition of a tool exposed by an MCP server."""
    name: str
    description: str
    handler: Callable[[Dict[str, Any]], Any]
    input_schema: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {},
        "required": [],
    })
    permissions: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  Structured JSON logger
# ═══════════════════════════════════════════════════════════════

class MCPLogger:
    """Structured JSON-line logger for MCP servers."""

    def __init__(self, server_name: str):
        self.server_name = server_name
        self._logger = logging.getLogger(f"mcp.{server_name}")
        self._logger.setLevel(logging.INFO)
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter(
                '{"ts":"%(asctime)s","server":"' + server_name + '",'
                '"level":"%(levelname)s","msg":"%(message)s"}',
                datefmt="%Y-%m-%dT%H:%M:%S",
            ))
            self._logger.addHandler(handler)

    def info(self, msg: str, **extra):
        self._logger.info(self._format(msg, **extra))

    def warning(self, msg: str, **extra):
        self._logger.warning(self._format(msg, **extra))

    def error(self, msg: str, **extra):
        self._logger.error(self._format(msg, **extra))

    def _format(self, msg: str, **extra) -> str:
        if extra:
            parts = [msg] + [f"{k}={v}" for k, v in extra.items()]
            return " | ".join(parts)
        return msg


# ═══════════════════════════════════════════════════════════════
#  Base MCP Server
# ═══════════════════════════════════════════════════════════════

class BaseMCPServer:
    """Base class for MCP-compatible tool servers.

    Subclass and call register_tool() to add tools, then run() to start.
    """

    def __init__(
        self,
        name: str,
        port: int = 9100,
        host: str = "127.0.0.1",
        api_key: Optional[str] = None,
        description: str = "",
    ):
        self.name = name
        self.port = port
        self.host = host
        self.api_key = api_key
        self.description = description
        self.log = MCPLogger(name)
        self._tools: Dict[str, MCPToolDef] = {}

        # Build FastAPI app
        self.app = FastAPI(
            title=f"MCP Server: {name}",
            description=description or f"MCP Server for {name}",
            version="1.0.0",
        )

        # CORS (allow localhost + LAN)
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["POST", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization", "X-API-Key"],
        )

        # Register the main JSON-RPC endpoint
        @self.app.post("/")
        async def handle_jsonrpc(request: Request):
            return await self._handle_request(request)

        @self.app.get("/health")
        async def health():
            return {"status": "ok", "server": self.name, "tools": len(self._tools)}

        self.log.info(
            f"Server initialized | port={port} | "
            f"auth={'on' if api_key else 'off'}"
        )

    # ── Tool registration ────────────────────────────────────

    def register_tool(self, tool: MCPToolDef) -> None:
        """Register a tool with this server."""
        self._tools[tool.name] = tool
        self.log.info(f"Registered tool: {tool.name}")

    def register_tools(self, tools: List[MCPToolDef]) -> None:
        """Register multiple tools at once."""
        for tool in tools:
            self.register_tool(tool)

    # ── Request handling ─────────────────────────────────────

    async def _handle_request(self, request: Request) -> JSONResponse:
        """Main JSON-RPC dispatcher."""
        start = time.perf_counter()
        body = await request.json()
        method = body.get("method", "")
        req_id = body.get("id", 1)
        params = body.get("params", {})

        # Auth check
        if self.api_key:
            auth_header = request.headers.get("Authorization", "")
            api_key_header = request.headers.get("X-API-Key", "")
            token = ""
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
            elif api_key_header:
                token = api_key_header

            if token != self.api_key:
                elapsed = (time.perf_counter() - start) * 1000
                self.log.warning(f"auth_failed | method={method} | elapsed={elapsed:.0f}ms")
                return self._error_response(req_id, -32001, "Unauthorized: invalid API key")

        # Route
        try:
            if method == "tools/list":
                result = await self._handle_list_tools()
            elif method == "tools/call":
                result = await self._handle_call_tool(params)
            else:
                return self._error_response(req_id, -32601, f"Method not found: {method}")

            elapsed = (time.perf_counter() - start) * 1000
            self.log.info(f"method={method} | status=ok | elapsed={elapsed:.0f}ms")
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result,
            })

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            self.log.error(f"method={method} | status=error | elapsed={elapsed:.0f}ms | error={exc}")
            return self._error_response(req_id, -32603, str(exc))

    async def _handle_list_tools(self) -> Dict[str, Any]:
        """Handle tools/list — return all registered tools with JSON Schema."""
        tools = []
        for name, tool in self._tools.items():
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
            })
        return {"tools": tools, "count": len(tools)}

    async def _handle_call_tool(self, params: Dict[str, Any]) -> Any:
        """Handle tools/call — invoke a registered tool."""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        tool = self._tools.get(tool_name)
        if tool is None:
            raise ValueError(f"Tool not found: {tool_name}")

        # Permission check
        if tool.permissions:
            requested_perms = arguments.pop("_permissions", [])
            for p in tool.permissions:
                if p not in requested_perms:
                    raise PermissionError(f"Missing required permission: {p}")

        # Execute
        self.log.info(f"tool_call | tool={tool_name}")
        result = tool.handler(arguments)
        return result

    @staticmethod
    def _error_response(req_id: int, code: int, message: str) -> JSONResponse:
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        }, status_code=200)  # JSON-RPC errors are still HTTP 200

    # ── Run ───────────────────────────────────────────────────

    def run(self) -> None:
        """Start the MCP server (blocking)."""
        self.log.info(f"Starting MCP server on {self.host}:{self.port}")
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="warning",  # suppress uvicorn access logs, we have our own
        )
