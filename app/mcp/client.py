"""
MCP Client — unified JSON-RPC 2.0 client for MCP server communication.

Supports:
  - HTTP transport (primary)
  - tool discovery (list_tools)
  - tool invocation (call_tool)
  - async + sync APIs
  - configurable timeout & retry
  - structured error handling

Does NOT support:
  - LLM directly calling MCP (that's the Agent's job through Provider layer)
  - Hardcoding tools in prompts
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

import httpx

from app.core.logging import logger
from app.mcp.models import (
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    MCPAuthType,
    MCPServerConfig,
    MCPTool,
    MCPToolCallResult,
    MCPToolSchema,
    MCPTransport,
)


# ═══════════════════════════════════════════════════════════════
#  Exceptions
# ═══════════════════════════════════════════════════════════════

class MCPError(Exception):
    """Base exception for MCP client errors."""


class MCPConnectionError(MCPError):
    """Failed to connect to the MCP server."""


class MCPTimeoutError(MCPError):
    """Request to MCP server timed out."""


class MCPProtocolError(MCPError):
    """JSON-RPC protocol error returned by the server."""


class MCPToolNotFoundError(MCPError):
    """Requested tool not found on the MCP server."""


# ═══════════════════════════════════════════════════════════════
#  HTTP Transport
# ═══════════════════════════════════════════════════════════════

class MCPClient:
    """JSON-RPC 2.0 client for a single MCP server endpoint.

    Usage:
        config = MCPServerConfig(name="car-data", base_url="http://localhost:9000")
        client = MCPClient(config)
        tools = await client.list_tools()
        result = await client.call_tool("search_car", {"brand": "Tesla"})
    """

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._request_id = 0
        self._tools_cache: Optional[List[MCPTool]] = None
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=float(self.config.timeout_seconds))
        return self._http_client

    async def aclose(self) -> None:
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    # ── Public API ──────────────────────────────────────────

    async def list_tools(self, refresh: bool = False) -> List[MCPTool]:
        """Discover available tools from the MCP server.

        Results are cached after first call; use refresh=True to force re-fetch.
        """
        if self._tools_cache is not None and not refresh:
            return self._tools_cache

        result = await self._call("tools/list")
        tools: List[MCPTool] = []

        if isinstance(result, list):
            for item in result:
                tools.append(self._parse_tool(item))
        elif isinstance(result, dict):
            tool_list = result.get("tools", result.get("data", [result]))
            if isinstance(tool_list, list):
                for item in tool_list:
                    tools.append(self._parse_tool(item))

        self._tools_cache = tools
        logger.info(
            f"[MCP:{self.config.name}] Discovered {len(tools)} tools: "
            f"{[t.name for t in tools]}"
        )
        return tools

    async def call_tool(
        self,
        tool_name: str,
        params: Optional[Dict[str, Any]] = None,
        timeout_override: Optional[int] = None,
    ) -> MCPToolCallResult:
        """Invoke a specific tool on the MCP server."""
        params = params or {}
        start = time.perf_counter()

        try:
            result = await self._call(
                "tools/call",
                {"name": tool_name, "arguments": params},
                timeout_override=timeout_override,
            )
            elapsed = (time.perf_counter() - start) * 1000

            logger.info(
                f"[MCP:{self.config.name}] call_tool '{tool_name}' "
                f"→ success ({elapsed:.0f}ms)"
            )
            return MCPToolCallResult(
                tool_name=tool_name,
                success=True,
                data=result,
                latency_ms=round(elapsed, 1),
            )

        except MCPError as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.warning(
                f"[MCP:{self.config.name}] call_tool '{tool_name}' "
                f"→ failed ({elapsed:.0f}ms): {exc}"
            )
            return MCPToolCallResult(
                tool_name=tool_name,
                success=False,
                error=str(exc),
                latency_ms=round(elapsed, 1),
            )

    def list_tools_sync(self, refresh: bool = False) -> List[MCPTool]:
        """Synchronous wrapper for list_tools."""
        return asyncio.run(self.list_tools(refresh=refresh))

    def call_tool_sync(
        self,
        tool_name: str,
        params: Optional[Dict[str, Any]] = None,
        timeout_override: Optional[int] = None,
    ) -> MCPToolCallResult:
        """Synchronous wrapper for call_tool."""
        return asyncio.run(self.call_tool(tool_name, params, timeout_override))

    # ── Internal ─────────────────────────────────────────────

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _parse_tool(self, raw: Dict[str, Any]) -> MCPTool:
        """Parse a raw tool dict from MCP response into an MCPTool."""
        schema_raw = raw.get("inputSchema", raw.get("input_schema", {}))
        return MCPTool(
            name=raw.get("name", "unknown"),
            description=raw.get("description", ""),
            input_schema=MCPToolSchema(
                type=schema_raw.get("type", "object"),
                properties=schema_raw.get("properties", {}),
                required=schema_raw.get("required", []),
            ),
            server_name=self.config.name,
            server_id=self.config.config_id,
        )

    async def _call(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout_override: Optional[int] = None,
    ) -> Any:
        """Execute a JSON-RPC call against the MCP server with retry support."""
        request = JSONRPCRequest(method=method, params=params or {}, req_id=self._next_id())
        timeout = timeout_override or self.config.timeout_seconds
        max_retries = self.config.max_retries + 1  # +1 for initial attempt

        last_error: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                if self.config.transport == MCPTransport.STDIO:
                    return await self._call_stdio(request, timeout)
                else:
                    return await self._call_http(request, timeout)
            except (MCPConnectionError, MCPTimeoutError) as exc:
                last_error = exc
                if attempt < max_retries - 1:
                    wait = 0.5 * (2 ** attempt)  # exponential backoff
                    logger.warning(
                        f"[MCP:{self.config.name}] {method} attempt {attempt + 1} failed, "
                        f"retrying in {wait:.1f}s: {exc}"
                    )
                    await asyncio.sleep(wait)
                else:
                    raise
            except MCPProtocolError:
                raise  # don't retry protocol errors

        raise last_error  # type: ignore[misc]

    async def _call_http(self, request: JSONRPCRequest, timeout: int) -> Any:
        """Execute JSON-RPC call over HTTP transport."""
        if not self.config.base_url:
            raise MCPConnectionError(f"MCP server '{self.config.name}' has no base_url configured")

        url = self.config.base_url.rstrip("/") + "/"
        headers = self._build_headers()

        try:
            client = await self._get_http_client()
            resp = await client.post(url, json={
                "jsonrpc": request.jsonrpc,
                "method": request.method,
                "params": request.params,
                "id": request.req_id,
            }, headers=headers, timeout=float(timeout))

            if resp.status_code != 200:
                raise MCPConnectionError(
                    f"HTTP {resp.status_code} from {self.config.name}: {resp.text[:300]}"
                )
            return self._parse_response(resp.json())

        except httpx.TimeoutException:
            raise MCPTimeoutError(
                f"MCP server '{self.config.name}' timed out after {timeout}s"
            )
        except httpx.ConnectError as exc:
            raise MCPConnectionError(
                f"Cannot connect to MCP server '{self.config.name}' at {url}: {exc}"
            )

    async def _call_stdio(self, request: JSONRPCRequest, timeout: int) -> Any:
        """Execute JSON-RPC call over stdio transport (subprocess).

        Note: Full stdio MCP server support (with initialization handshake)
        will be added when we implement the actual MCP server subprocesses.
        For now, this is a placeholder for the protocol.
        """
        raise MCPConnectionError(
            f"STDIO transport not yet implemented for '{self.config.name}'. "
            f"Please configure an HTTP transport URL."
        )

    def _parse_response(self, raw: Dict[str, Any]) -> Any:
        """Parse a JSON-RPC response, raising on errors."""
        error_data = raw.get("error")
        if error_data is not None:
            err = JSONRPCError(
                code=error_data.get("code", -1),
                message=error_data.get("message", "Unknown error"),
                data=error_data.get("data"),
            )
            if err.code == -32601:  # Method not found
                raise MCPToolNotFoundError(
                    f"MCP server '{self.config.name}': {err.message}"
                )
            raise MCPProtocolError(
                f"[{err.code}] {err.message}" + (f" — {err.data}" if err.data else "")
            )

        return raw.get("result")

    def _build_headers(self) -> Dict[str, str]:
        """Build HTTP headers including authentication."""
        headers = {"Content-Type": "application/json"}

        if self.config.auth_type == MCPAuthType.BEARER:
            token = self.config.auth_config.get("token", "")
            if token:
                headers["Authorization"] = f"Bearer {token}"

        elif self.config.auth_type == MCPAuthType.API_KEY:
            key = self.config.auth_config.get("api_key", "")
            header_name = self.config.auth_config.get("header_name", "X-API-Key")
            if key:
                headers[header_name] = key

        return headers


# ═══════════════════════════════════════════════════════════════
#  Client Factory
# ═══════════════════════════════════════════════════════════════

class MCPClientFactory:
    """Creates and caches MCPClient instances by server config."""

    def __init__(self):
        self._clients: Dict[str, MCPClient] = {}

    def get_client(self, config: MCPServerConfig) -> MCPClient:
        """Get or create an MCPClient for the given config."""
        cache_key = config.name
        if cache_key not in self._clients:
            self._clients[cache_key] = MCPClient(config)
        return self._clients[cache_key]

    def invalidate(self, server_name: str) -> None:
        """Remove a cached client (e.g., after config update)."""
        self._clients.pop(server_name, None)

    async def ainvalidate(self, server_name: str) -> None:
        """Async version that properly closes HTTP connections."""
        client = self._clients.pop(server_name, None)
        if client is not None:
            await client.aclose()

    def clear(self) -> None:
        """Clear all cached clients."""
        self._clients.clear()


# Module-level singleton
mcp_client_factory = MCPClientFactory()
