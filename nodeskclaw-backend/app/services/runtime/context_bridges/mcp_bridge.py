"""MCPContextBridge — exposes workspace context via MCP server protocol."""

from __future__ import annotations

import logging

from app.services.runtime.context_bridges.base import WorkspaceContext

logger = logging.getLogger(__name__)


class MCPContextBridge:
    bridge_id = "mcp"

    async def inject_context(
        self,
        instance_id: str,
        workspace_id: str,
        context: WorkspaceContext,
    ) -> None:
        logger.debug(
            "MCPContextBridge.inject_context: instance=%s workspace=%s",
            instance_id, workspace_id,
        )

    async def remove_context(
        self,
        instance_id: str,
        workspace_id: str,
    ) -> None:
        logger.debug(
            "MCPContextBridge.remove_context: instance=%s workspace=%s",
            instance_id, workspace_id,
        )
