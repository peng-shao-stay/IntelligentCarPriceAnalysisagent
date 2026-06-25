"""
MCP Provider Adapter — bridges MCP tool calls to Provider interfaces.

This module allows MCP-discovered tools to be used through the same
Provider interfaces that the Agent already depends on.

Flow:
  DB (mcp_server_configs) → MCPServerConfig → MCPClient → Provider interface

Essential servers (like DuckDuckGo) remain direct Provider implementations.
Non-essential servers can be managed via MCP from the frontend.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db.models import MCPServerConfig as MCPServerConfigModel
from app.mcp.client import MCPClient, MCPClientFactory
from app.mcp.models import MCPServerConfig, MCPTool
from app.providers.base import SearchProvider


# ═══════════════════════════════════════════════════════════════
#  Config loader: DB → runtime configs
# ═══════════════════════════════════════════════════════════════

class MCPConfigService:
    """Loads MCP server configurations from the database and manages MCP clients."""

    def __init__(self, client_factory: MCPClientFactory = None):
        self._client_factory = client_factory or MCPClientFactory()
        self._configs: Dict[str, MCPServerConfig] = {}
        self._tools: Dict[str, List[MCPTool]] = {}

    def load_from_db(self, db: Session) -> List[MCPServerConfig]:
        """Load all enabled MCP server configs from the database."""
        rows = (
            db.query(MCPServerConfigModel)
            .filter(
                MCPServerConfigModel.is_deleted == False,
                MCPServerConfigModel.is_enabled == True,
            )
            .all()
        )

        configs: List[MCPServerConfig] = []
        for row in rows:
            config = MCPServerConfig.model_validate(row)
            configs.append(config)
            self._configs[config.name] = config

        logger.info(
            f"[MCPConfigService] Loaded {len(configs)} MCP server configs: "
            f"{[c.name for c in configs]}"
        )
        return configs

    def get_config(self, name: str) -> Optional[MCPServerConfig]:
        """Get a loaded config by name."""
        return self._configs.get(name)

    def get_client(self, name: str) -> Optional[MCPClient]:
        """Get or create an MCP client for a named server."""
        config = self._configs.get(name)
        if config is None:
            return None
        return self._client_factory.get_client(config)

    async def discover_all_tools(self) -> Dict[str, List[MCPTool]]:
        """Discover tools from all loaded MCP servers."""
        self._tools = {}
        for name, config in self._configs.items():
            client = self._client_factory.get_client(config)
            try:
                tools = await client.list_tools(refresh=True)
                self._tools[name] = tools
            except Exception as exc:
                logger.warning(f"[MCPConfigService] Failed to discover tools from '{name}': {exc}")
                self._tools[name] = []
        return self._tools

    def discover_all_tools_sync(self) -> Dict[str, List[MCPTool]]:
        """Synchronous wrapper for discover_all_tools."""
        return asyncio.run(self.discover_all_tools())

    def get_tools(self, server_name: str) -> List[MCPTool]:
        """Get cached tools for a server."""
        return self._tools.get(server_name, [])

    def get_all_tools(self) -> List[MCPTool]:
        """Get all tools from all servers as a flat list."""
        result: List[MCPTool] = []
        for tools in self._tools.values():
            result.extend(tools)
        return result

    def invalidate(self, server_name: str) -> None:
        """Clear cache for a server (after config update)."""
        self._configs.pop(server_name, None)
        self._tools.pop(server_name, None)
        self._client_factory.invalidate(server_name)

    def clear(self) -> None:
        """Clear all cached configs, tools, and clients."""
        self._configs.clear()
        self._tools.clear()
        self._client_factory.clear()


# ═══════════════════════════════════════════════════════════════
#  MCP → Provider adapters
# ═══════════════════════════════════════════════════════════════

class MCPEnabledSearchProvider(SearchProvider):
    """SearchProvider that routes through MCP when available, falls back to primary.

    This preserves DuckDuckGo as the essential search backend while allowing
    additional MCP-based search servers to contribute results.
    """

    def __init__(
        self,
        primary: SearchProvider,  # essential — DuckDuckGo
        config_service: MCPConfigService,
    ):
        self._primary = primary
        self._config_svc = config_service

    @property
    def is_available(self) -> bool:
        return self._primary.is_available

    def _call_mcp_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
        server_name: str,
    ) -> Optional[Any]:
        """Call an MCP tool and return its data, or None on failure."""
        client = self._config_svc.get_client(server_name)
        if client is None:
            return None
        result = client.call_tool_sync(tool_name, params)
        if result.success:
            return result.data
        return None

    # ── SearchProvider interface ────────────────────────────

    def search_car_price(
        self,
        brand: str,
        model: str,
        version: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        # Primary: DuckDuckGo
        results = self._primary.search_car_price(brand=brand, model=model, version=version)

        # Augment: try MCP car-data server for structured specs
        mcp_data = self._call_mcp_tool(
            "search_car",
            {"brand": brand, "model": model, "version": version or ""},
            "car-data",
        )
        if mcp_data and isinstance(mcp_data, list):
            for item in mcp_data:
                if isinstance(item, dict):
                    results.append({**item, "source": "MCP car-data"})

        return results

    def search_news(
        self,
        keyword: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        return self._primary.search_news(keyword=keyword, limit=limit)

    def search_general(
        self,
        query: str,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        return self._primary.search_general(query=query, max_results=max_results)

    def search_comparison(
        self,
        car1_brand: str,
        car1_model: str,
        car2_brand: str,
        car2_model: str,
    ) -> Dict[str, Any]:
        return self._primary.search_comparison(
            car1_brand=car1_brand,
            car1_model=car1_model,
            car2_brand=car2_brand,
            car2_model=car2_model,
        )


# Module-level singleton
mcp_config_service = MCPConfigService()
