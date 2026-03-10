"""ContextBridge — protocol for injecting workspace context into agent runtimes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class WorkspaceContext:
    workspace_id: str
    workspace_name: str
    agent_identity: str
    team: list[dict] = field(default_factory=list)
    recent_messages: list[dict] = field(default_factory=list)
    reachable_nodes: list[dict] = field(default_factory=list)
    collaboration_rules: dict = field(default_factory=dict)
    blackboard_state: dict = field(default_factory=dict)


class ContextBridge(Protocol):
    async def inject_context(
        self,
        instance_id: str,
        workspace_id: str,
        context: WorkspaceContext,
    ) -> None:
        """Push workspace context to the agent runtime."""
        ...

    async def remove_context(
        self,
        instance_id: str,
        workspace_id: str,
    ) -> None:
        """Remove workspace context from the agent runtime."""
        ...
