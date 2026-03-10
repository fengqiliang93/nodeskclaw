"""SystemPromptBridge — injects workspace context into the LLM system message."""

from __future__ import annotations

import logging

from app.services.runtime.context_bridges.base import WorkspaceContext

logger = logging.getLogger(__name__)


class SystemPromptBridge:
    bridge_id = "system_prompt"

    async def inject_context(
        self,
        instance_id: str,
        workspace_id: str,
        context: WorkspaceContext,
    ) -> None:
        logger.debug(
            "SystemPromptBridge.inject_context: instance=%s workspace=%s",
            instance_id, workspace_id,
        )

    async def remove_context(
        self,
        instance_id: str,
        workspace_id: str,
    ) -> None:
        pass

    def build_system_prompt(self, context: WorkspaceContext) -> str:
        """Build a system prompt string from workspace context."""
        parts = [
            f"你是 {context.agent_identity}，在赛博办公室「{context.workspace_name}」中工作。",
        ]

        if context.team:
            team_lines = []
            for member in context.team:
                team_lines.append(f"- [{member.get('type', 'unknown')}] {member.get('name', '?')}")
            parts.append("\n团队成员:\n" + "\n".join(team_lines))

        if context.recent_messages:
            msg_lines = []
            for msg in context.recent_messages[-20:]:
                msg_lines.append(f"[{msg.get('sender_name', '?')}]: {msg.get('content', '')[:200]}")
            parts.append("\n最近消息:\n" + "\n".join(msg_lines))

        return "\n\n".join(parts)
