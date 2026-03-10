"""ContextBridgeRegistry — maps context bridge identifiers to ContextBridge factories."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ContextBridgeSpec:
    bridge_id: str
    description: str | None = None
    config_schema: dict | None = None


class ContextBridgeRegistry:
    def __init__(self) -> None:
        self._bridges: dict[str, ContextBridgeSpec] = {}
        self._factories: dict[str, Any] = {}

    def register(self, spec: ContextBridgeSpec, factory: Any = None) -> None:
        self._bridges[spec.bridge_id] = spec
        if factory is not None:
            self._factories[spec.bridge_id] = factory
        logger.debug("Registered context bridge: %s", spec.bridge_id)

    def get(self, bridge_id: str) -> ContextBridgeSpec | None:
        return self._bridges.get(bridge_id)

    def get_factory(self, bridge_id: str) -> Any | None:
        return self._factories.get(bridge_id)

    def all_bridges(self) -> list[ContextBridgeSpec]:
        return list(self._bridges.values())


CONTEXT_BRIDGE_REGISTRY = ContextBridgeRegistry()

CONTEXT_BRIDGE_REGISTRY.register(ContextBridgeSpec(
    bridge_id="channel_plugin",
    description="Channel Plugin bridge — writes context via filesystem to agent workspace.",
))

CONTEXT_BRIDGE_REGISTRY.register(ContextBridgeSpec(
    bridge_id="mcp",
    description="MCP bridge — exposes workspace context via MCP server protocol.",
))

CONTEXT_BRIDGE_REGISTRY.register(ContextBridgeSpec(
    bridge_id="system_prompt",
    description="System Prompt bridge — injects context into LLM system message.",
))
