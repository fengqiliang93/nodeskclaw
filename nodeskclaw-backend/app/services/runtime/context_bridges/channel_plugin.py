"""ChannelPluginBridge — injects workspace context via Channel Plugin file writes."""

from __future__ import annotations

import logging

from app.services.runtime.context_bridges.base import WorkspaceContext

logger = logging.getLogger(__name__)


class ChannelPluginBridge:
    bridge_id = "channel_plugin"

    async def inject_context(
        self,
        instance_id: str,
        workspace_id: str,
        context: WorkspaceContext,
    ) -> None:
        logger.debug(
            "ChannelPluginBridge.inject_context: instance=%s workspace=%s",
            instance_id, workspace_id,
        )

    async def remove_context(
        self,
        instance_id: str,
        workspace_id: str,
    ) -> None:
        logger.debug(
            "ChannelPluginBridge.remove_context: instance=%s workspace=%s",
            instance_id, workspace_id,
        )
