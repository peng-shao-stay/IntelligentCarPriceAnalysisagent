"""
Tool Discovery Service — dynamically loads MCP server configs from the database,
discovers tools, and builds a unified ToolRegistry at agent startup.

This bridges the gap between static built-in tools and MCP-discovered tools,
giving the Agent a complete picture of all available capabilities.

Flow:
  1. Load enabled MCP server configs from DB
  2. For each server, call tools/list via MCPClient
  3. Convert MCPTool → AgentTool with a generic MCP handler
  4. Merge with built-in tools into a unified ToolRegistry
  5. Generate dynamic system prompt section
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.agent.tool_registry import AgentTool, ToolExecutionResult, ToolRegistry
from app.core.logging import logger
from app.mcp.client import MCPClient, mcp_client_factory
from app.mcp.models import MCPServerConfig, MCPTool


# ═══════════════════════════════════════════════════════════════
#  DB → Runtime config loader
# ═══════════════════════════════════════════════════════════════

def _load_mcp_configs_from_db(db) -> List[MCPServerConfig]:
    from app.db.models import MCPServerConfig as MCPServerConfigModel

    rows = (
        db.query(MCPServerConfigModel)
        .filter(
            MCPServerConfigModel.is_deleted == False,
            MCPServerConfigModel.is_enabled == True,
        )
        .all()
    )

    configs = [MCPServerConfig.model_validate(row) for row in rows]

    logger.info(f"[Discovery] Loaded {len(configs)} MCP server configs from DB")
    return configs


# ═══════════════════════════════════════════════════════════════
#  Generic MCP tool handler factory
# ═══════════════════════════════════════════════════════════════

def _make_mcp_handler(
    server_config: MCPServerConfig,
    mcp_tool: MCPTool,
) -> Any:
    """Create a handler function that calls an MCP tool.

    Returns a callable compatible with AgentTool.handler signature:
        handler(message: str, history: List[Dict] | None) -> ToolExecutionResult
    """

    def handler(message: str, history: Optional[List[Dict]] = None) -> ToolExecutionResult:
        tool_name = mcp_tool.name
        logger.info(f"[MCP Handler] Calling '{tool_name}' on '{server_config.name}'")

        try:
            client = mcp_client_factory.get_client(server_config)
            params = _extract_params_from_message(message, mcp_tool)
            result = client.call_tool_sync(tool_name, params)

            if result.success:
                return ToolExecutionResult(
                    tool_name=tool_name,
                    success=True,
                    payload={
                        "server": server_config.name,
                        "tool": tool_name,
                        "data": result.data,
                        "latency_ms": result.latency_ms,
                    },
                    summary=_format_mcp_result(tool_name, result.data),
                )
            else:
                return ToolExecutionResult(
                    tool_name=tool_name,
                    success=False,
                    payload={"error": result.error},
                    summary=f"MCP 工具 '{tool_name}' 调用失败: {result.error}",
                )

        except Exception as exc:
            logger.warning(f"[MCP Handler] '{tool_name}' error: {exc}")
            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                payload={"error": str(exc)},
                summary=f"调用 MCP 服务 '{server_config.name}' 时出错: {exc}",
            )

    return handler


def _extract_params_from_message(message: str, mcp_tool: MCPTool) -> Dict[str, Any]:
    """Extract tool parameters from a user message using the tool's input schema.

    For Phase 3, this uses a simple heuristic:
      - String properties: try to extract car brand/model from message
      - Number properties: try to find numbers in message
      - Falls back to {"query": message} for unknown schemas
    """
    schema = mcp_tool.input_schema
    properties = schema.properties if schema else {}
    if not properties:
        return {"query": message}

    params: Dict[str, Any] = {}

    for prop_name, prop_schema in properties.items():
        prop_type = prop_schema.get("type", "string") if isinstance(prop_schema, dict) else "string"

        if prop_type == "string":
            if prop_name in ("brand", "make"):
                params[prop_name] = _guess_brand(message)
            elif prop_name in ("model", "car_model"):
                params[prop_name] = _guess_model(message)
            elif prop_name in ("query", "keyword", "q", "search"):
                params[prop_name] = message
            else:
                params[prop_name] = message

        elif prop_type in ("number", "integer"):
            nums = re.findall(r"\d+\.?\d*", message)
            if nums:
                try:
                    params[prop_name] = float(nums[0]) if prop_type == "number" else int(float(nums[0]))
                except ValueError:
                    pass

        elif prop_type == "boolean":
            params[prop_name] = "true" not in message.lower()

    # Always include raw query
    if "query" not in params:
        params["query"] = message

    return params


def _guess_brand(message: str) -> str:
    """Guess car brand from message."""
    brands = [
        "特斯拉", "比亚迪", "蔚来", "理想", "小鹏", "小米",
        "大众", "丰田", "本田", "宝马", "奔驰", "奥迪",
        "吉利", "长城", "长安", "奇瑞", "领克", "极氪",
        "问界", "阿维塔", "智己", "岚图", "零跑", "哪吒",
    ]
    for brand in brands:
        if brand in message:
            return brand
    return ""


def _guess_model(message: str) -> str:
    """Guess car model from message."""
    models = [
        "Model 3", "Model Y", "Model S", "Model X",
        "汉", "唐", "宋", "秦", "海豹", "海豚",
        "ET5", "ET7", "ES6", "ES8", "EC6",
        "L7", "L8", "L9", "ONE",
        "P7", "G9", "G6",
        "SU7",
        "M7", "M9", "M5",
        "001", "007", "X",
        "ID.3", "ID.4", "ID.6",
        "卡罗拉", "凯美瑞", "雅阁", "思域",
        "3系", "5系", "C级", "E级", "A4", "A6",
    ]
    for model in sorted(models, key=len, reverse=True):  # longer match first
        if model.lower() in message.lower():
            return model
    return ""


def _format_mcp_result(tool_name: str, data: Any) -> str:
    """Format MCP tool result into a summary string."""
    if isinstance(data, str):
        return data[:500]
    if isinstance(data, list):
        count = len(data)
        preview = ", ".join(
            str(item.get("title", item.get("name", "")))
            for item in data[:3]
            if isinstance(item, dict)
        )
        return f"获取到 {count} 条结果: {preview}" if preview else f"获取到 {count} 条结果"
    if isinstance(data, dict):
        keys = list(data.keys())
        return f"返回数据，包含字段: {', '.join(keys[:10])}"
    return str(data)[:300]


# ═══════════════════════════════════════════════════════════════
#  Discovery orchestrator
# ═══════════════════════════════════════════════════════════════

class ToolDiscoveryService:
    """Orchestrates MCP tool discovery and merges results into a ToolRegistry."""

    def __init__(self):
        self._discovered_tools: Dict[str, List[MCPTool]] = {}    # server_name → tools
        self._configs: Dict[str, MCPServerConfig] = {}

    # ── Discovery ─────────────────────────────────────────────

    def discover_from_db(self, db) -> List[MCPTool]:
        """Load MCP configs from DB and discover tools from all enabled servers.

        Returns a flat list of all discovered MCPTool instances.
        """
        configs = _load_mcp_configs_from_db(db)
        all_tools: List[MCPTool] = []

        for config in configs:
            self._configs[config.name] = config
            try:
                client = MCPClient(config)
                tools = client.list_tools_sync(refresh=True)

                # Tag each tool with server info
                for tool in tools:
                    tool.server_name = config.name
                    tool.server_id = config.config_id

                self._discovered_tools[config.name] = tools
                all_tools.extend(tools)

                # Persist discovered schemas back to DB
                self._save_tool_schemas(db, config, tools)

                logger.info(
                    f"[Discovery] '{config.name}': {len(tools)} tools — "
                    f"{[t.name for t in tools]}"
                )
            except Exception as exc:
                logger.warning(
                    f"[Discovery] Failed to discover tools from '{config.name}': {exc}"
                )
                # Use cached schemas from DB if available
                cached = self._load_cached_tools(db, config)
                if cached:
                    self._discovered_tools[config.name] = cached
                    all_tools.extend(cached)
                    logger.info(
                        f"[Discovery] '{config.name}': using {len(cached)} cached tools"
                    )

        return all_tools

    def _save_tool_schemas(self, db, config: MCPServerConfig, tools: List[MCPTool]) -> None:
        """Persist discovered tool schemas to the database."""
        try:
            from app.db.models import MCPServerConfig as MCPServerConfigModel

            row = (
                db.query(MCPServerConfigModel)
                .filter(MCPServerConfigModel.id == config.config_id)
                .first()
            )
            if row:
                row.tool_schemas = [t.to_dict() for t in tools]
                db.commit()
        except Exception as exc:
            logger.warning(f"[Discovery] Failed to save tool schemas for '{config.name}': {exc}")
            db.rollback()

    def _load_cached_tools(self, db, config: MCPServerConfig) -> List[MCPTool]:
        """Load cached tool schemas from DB when live discovery fails."""
        try:
            from app.db.models import MCPServerConfig as MCPServerConfigModel

            row = (
                db.query(MCPServerConfigModel)
                .filter(MCPServerConfigModel.id == config.config_id)
                .first()
            )
            if row and row.tool_schemas:
                tools = []
                for t in row.tool_schemas:
                    tools.append(MCPTool(
                        name=t.get("name", "unknown"),
                        description=t.get("description", ""),
                        server_name=config.name,
                        server_id=config.config_id,
                    ))
                return tools
        except Exception as exc:
            logger.warning(f"[Discovery] Failed to load cached tools for '{config.name}': {exc}")
        return []

    # ── Registry building ────────────────────────────────────

    def build_unified_registry(
        self,
        builtin_registry: ToolRegistry,
    ) -> ToolRegistry:
        """Merge built-in tools with MCP-discovered tools into a unified registry.

        Built-in tools take priority — MCP tools with conflicting intents are skipped.
        MCP tools get their intent auto-assigned based on name/description heuristics.
        """
        registry = ToolRegistry()

        # 1. Register built-in tools first (priority)
        for tool in builtin_registry.list_tools():
            registry.register(tool)

        # 2. Register MCP-discovered tools
        registered_intents = {t.intent for t in registry.list_tools()}
        for server_name, tools in self._discovered_tools.items():
            config = self._configs.get(server_name)
            if config is None:
                continue

            for mcp_tool in tools:
                intent = _infer_intent(mcp_tool)
                # Avoid overwriting built-in tools
                if intent in registered_intents:
                    logger.info(
                        f"[Discovery] Skipping MCP tool '{mcp_tool.name}' "
                        f"(intent '{intent}' already handled by built-in tool)"
                    )
                    continue

                handler = _make_mcp_handler(config, mcp_tool)
                agent_tool = AgentTool(
                    name=mcp_tool.name,
                    description=f"[MCP:{server_name}] {mcp_tool.description}",
                    intent=intent,
                    handler=handler,
                    source="mcp",
                    metadata={
                        "server_name": server_name,
                        "server_id": config.config_id,
                        "mcp_tool": mcp_tool.name,
                        "input_schema": mcp_tool.input_schema.properties if mcp_tool.input_schema else {},
                    },
                )
                registry.register(agent_tool)
                registered_intents.add(intent)
                logger.info(
                    f"[Discovery] Registered MCP tool '{mcp_tool.name}' "
                    f"from '{server_name}' with intent '{intent}'"
                )

        return registry

    # ── Prompt generation ────────────────────────────────────

    def build_tools_prompt_section(self, registry: ToolRegistry) -> str:
        """Generate the 'Available Tools' section for the system prompt."""
        tools = registry.list_tools()
        if not tools:
            return ""

        lines = [
            "## 可用工具",
            "",
            "你可以使用以下工具来回答用户的问题：",
            "",
        ]

        # Group by source
        builtins = [t for t in tools if getattr(t, 'source', None) != "mcp"]
        mcp_tools = [t for t in tools if getattr(t, 'source', None) == "mcp"]

        if builtins:
            lines.append("### 内置工具")
            for t in builtins:
                lines.append(f"- **{t.name}**: {t.description}")
            lines.append("")

        if mcp_tools:
            # Group MCP tools by server
            by_server: Dict[str, List[AgentTool]] = {}
            for t in mcp_tools:
                server = t.metadata.get("server_name", "unknown") if t.metadata else "unknown"
                by_server.setdefault(server, []).append(t)

            lines.append("### MCP 外部服务工具")
            for server, server_tools in by_server.items():
                lines.append(f"**{server}**:")
                for t in server_tools:
                    lines.append(f"- **{t.name}**: {t.description}")
            lines.append("")

        lines.append("使用规则：")
        lines.append("1. 根据用户问题选择最合适的工具")
        lines.append("2. 优先使用内置工具（速度更快）")
        lines.append("3. 当内置工具无法满足需求时，使用 MCP 外部工具")
        lines.append("4. 一次只使用一个工具，不要同时调用多个")

        return "\n".join(lines)


# ── Intent inference for MCP tools ───────────────────────────

def _infer_intent(tool: MCPTool) -> str:
    """Infer an intent category for an MCP tool based on its name and description."""
    name_lower = (tool.name + " " + tool.description).lower()

    price_kw = ["price", "价格", "报价", "售价", "cost"]
    compare_kw = ["compare", "对比", "比较", "vs", "diff"]
    news_kw = ["news", "新闻", "资讯", "article", "feed"]
    search_kw = ["search", "查询", "搜索", "find", "lookup"]
    vector_kw = ["vector", "embed", "语义", "similar", "rag", "retrieve"]
    spec_kw = ["spec", "配置", "参数", "detail", "info"]

    if any(kw in name_lower for kw in price_kw):
        return "car_price"
    if any(kw in name_lower for kw in compare_kw):
        return "car_compare"
    if any(kw in name_lower for kw in news_kw):
        return "news"
    if any(kw in name_lower for kw in vector_kw):
        return "car_price"     # vector search → car info lookup
    if any(kw in name_lower for kw in spec_kw):
        return "car_price"
    if any(kw in name_lower for kw in search_kw):
        return "general"

    return "general"


# Module-level singleton
discovery_service = ToolDiscoveryService()
