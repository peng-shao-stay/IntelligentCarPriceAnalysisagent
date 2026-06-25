"""
MCP server management API — admin only.

Endpoints:
  GET    /admin/mcp/servers          — list all MCP server configs
  POST   /admin/mcp/servers          — create a new config
  PUT    /admin/mcp/servers/{id}     — update a config
  DELETE /admin/mcp/servers/{id}     — soft-delete a config
  POST   /admin/mcp/servers/{id}/test     — test connection
  GET    /admin/mcp/servers/{id}/tools    — cached tool list
  POST   /admin/mcp/servers/{id}/discover — force tool rediscovery
"""

from datetime import datetime, timezone
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import admin_required, get_current_user
from app.core.logging import logger
from app.db.database import get_db
from app.db.models import MCPServerConfig as MCPServerConfigModel
from app.db.models import User
from app.mcp.adapter import mcp_config_service
from app.mcp.client import MCPClient
from app.mcp.models import MCPServerConfig, MCPTool
from app.schemas.mcp import (
    MCPServerCreate,
    MCPServerResponse,
    MCPServerUpdate,
    MCPTestResult,
    MCPToolResponse,
    MCPToolsListResponse,
)

router = APIRouter(
    prefix="/admin/mcp",
    tags=["MCP管理"],
    dependencies=[Depends(get_current_user), Depends(admin_required)],
)


def _model_to_response(m: MCPServerConfigModel) -> MCPServerResponse:
    """Convert ORM model to API response (masks auth_config)."""
    return MCPServerResponse(
        id=m.id,
        name=m.name,
        description=m.description or "",
        transport=m.transport,
        base_url=m.base_url or "",
        command=m.command or "",
        auth_type=m.auth_type,
        tool_schemas=m.tool_schemas or [],
        is_enabled=m.is_enabled,
        is_essential=m.is_essential,
        timeout_seconds=m.timeout_seconds,
        max_retries=m.max_retries,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


# ═══════════════════════════════════════════════════════════════
#  CRUD
# ═══════════════════════════════════════════════════════════════

@router.get("/servers", response_model=list[MCPServerResponse])
def list_servers(db: Session = Depends(get_db)):
    """List all MCP server configs (non-deleted)."""
    rows = (
        db.query(MCPServerConfigModel)
        .filter(MCPServerConfigModel.is_deleted == False)
        .order_by(MCPServerConfigModel.is_essential.desc(), MCPServerConfigModel.name)
        .all()
    )
    return [_model_to_response(r) for r in rows]


@router.post("/servers", response_model=MCPServerResponse)
def create_server(
    req: MCPServerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new MCP server configuration."""
    existing = (
        db.query(MCPServerConfigModel)
        .filter(
            MCPServerConfigModel.name == req.name,
            MCPServerConfigModel.is_deleted == False,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"Server '{req.name}' already exists")

    server = MCPServerConfigModel(
        name=req.name,
        description=req.description,
        transport=req.transport,
        base_url=req.base_url,
        command=req.command,
        env_vars=req.env_vars,
        auth_type=req.auth_type,
        auth_config=req.auth_config,
        is_enabled=req.is_enabled,
        is_essential=req.is_essential,
        timeout_seconds=req.timeout_seconds,
        max_retries=req.max_retries,
    )
    db.add(server)
    db.commit()
    db.refresh(server)

    logger.info(
        f"User {current_user.username} created MCP server '{server.name}' "
        f"(id={server.id}, transport={server.transport})"
    )
    return _model_to_response(server)


@router.put("/servers/{server_id}", response_model=MCPServerResponse)
def update_server(
    server_id: int,
    req: MCPServerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an MCP server configuration."""
    server = (
        db.query(MCPServerConfigModel)
        .filter(
            MCPServerConfigModel.id == server_id,
            MCPServerConfigModel.is_deleted == False,
        )
        .first()
    )
    if not server:
        raise HTTPException(status_code=404, detail="MCP server config not found")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(server, key, value)

    db.commit()
    db.refresh(server)

    # Invalidate cache so next request picks up changes
    mcp_config_service.invalidate(server.name)

    logger.info(
        f"User {current_user.username} updated MCP server '{server.name}' (id={server.id})"
    )
    return _model_to_response(server)


@router.delete("/servers/{server_id}")
def delete_server(
    server_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete an MCP server configuration."""
    server = (
        db.query(MCPServerConfigModel)
        .filter(
            MCPServerConfigModel.id == server_id,
            MCPServerConfigModel.is_deleted == False,
        )
        .first()
    )
    if not server:
        raise HTTPException(status_code=404, detail="MCP server config not found")

    if server.is_essential:
        raise HTTPException(status_code=403, detail="Cannot delete an essential MCP server")

    server.is_deleted = True
    server.deleted_at = datetime.now(timezone.utc)
    db.commit()

    mcp_config_service.invalidate(server.name)

    logger.info(
        f"User {current_user.username} deleted MCP server '{server.name}' (id={server.id})"
    )
    return {"message": f"MCP server '{server.name}' deleted"}


# ═══════════════════════════════════════════════════════════════
#  Actions
# ═══════════════════════════════════════════════════════════════

@router.post("/servers/{server_id}/test", response_model=MCPTestResult)
def test_connection(server_id: int, db: Session = Depends(get_db)):
    """Test connection to an MCP server and discover its tools."""
    server = (
        db.query(MCPServerConfigModel)
        .filter(
            MCPServerConfigModel.id == server_id,
            MCPServerConfigModel.is_deleted == False,
        )
        .first()
    )
    if not server:
        raise HTTPException(status_code=404, detail="MCP server config not found")

    start = time.perf_counter()

    config = MCPServerConfig.model_validate(server)
    client = MCPClient(config)

    try:
        tools = client.list_tools_sync(refresh=True)
        elapsed = (time.perf_counter() - start) * 1000

        # Persist discovered tool schemas
        server.tool_schemas = [t.to_dict() for t in tools]
        db.commit()

        # Update in-memory cache
        mcp_config_service._tools[server.name] = tools
        mcp_config_service._configs[server.name] = config

        return MCPTestResult(
            success=True,
            message=f"Connected successfully. Discovered {len(tools)} tools.",
            tools_found=len(tools),
            tool_names=[t.name for t in tools],
            latency_ms=round(elapsed, 1),
        )
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000
        logger.warning(f"MCP test connection failed for '{server.name}': {exc}")
        return MCPTestResult(
            success=False,
            message=f"Connection failed: {exc}",
            tools_found=0,
            tool_names=[],
            latency_ms=round(elapsed, 1),
        )


@router.get("/servers/{server_id}/tools", response_model=MCPToolsListResponse)
def get_server_tools(server_id: int, db: Session = Depends(get_db)):
    """Get cached tool list for an MCP server."""
    server = (
        db.query(MCPServerConfigModel)
        .filter(
            MCPServerConfigModel.id == server_id,
            MCPServerConfigModel.is_deleted == False,
        )
        .first()
    )
    if not server:
        raise HTTPException(status_code=404, detail="MCP server config not found")

    # Try cache first, then DB
    tools = mcp_config_service.get_tools(server.name)
    if not tools and server.tool_schemas:
        tools = [
            MCPTool(
                name=t.get("name", "unknown"),
                description=t.get("description", ""),
                server_name=server.name,
                server_id=server.id,
            )
            for t in server.tool_schemas
        ]

    return MCPToolsListResponse(
        server_name=server.name,
        tools=[MCPToolResponse(
            name=t.name,
            description=t.description,
            input_schema=t.input_schema.__dict__ if hasattr(t.input_schema, '__dict__') else {},
            server_name=t.server_name,
            server_id=t.server_id,
        ) for t in tools],
        count=len(tools),
    )


@router.post("/servers/{server_id}/discover", response_model=MCPToolsListResponse)
def discover_tools(server_id: int, db: Session = Depends(get_db)):
    """Force tool rediscovery for an MCP server."""
    server = (
        db.query(MCPServerConfigModel)
        .filter(
            MCPServerConfigModel.id == server_id,
            MCPServerConfigModel.is_deleted == False,
        )
        .first()
    )
    if not server:
        raise HTTPException(status_code=404, detail="MCP server config not found")

    config = MCPServerConfig.model_validate(server)
    client = MCPClient(config)

    try:
        tools = client.list_tools_sync(refresh=True)
        server.tool_schemas = [t.to_dict() for t in tools]
        db.commit()

        mcp_config_service._tools[server.name] = tools
        mcp_config_service._configs[server.name] = config

        return MCPToolsListResponse(
            server_name=server.name,
            tools=[MCPToolResponse(
                name=t.name,
                description=t.description,
                input_schema=t.input_schema.__dict__ if hasattr(t.input_schema, '__dict__') else {},
                server_name=t.server_name,
                server_id=t.server_id,
            ) for t in tools],
            count=len(tools),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Tool discovery failed: {exc}")
