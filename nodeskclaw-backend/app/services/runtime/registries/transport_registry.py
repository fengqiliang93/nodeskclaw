"""TransportRegistry — maps transport identifiers to transport adapter instances."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TransportSpec:
    transport_id: str
    adapter: Any = None
    description: str | None = None
    config_schema: dict | None = None


class TransportRegistry:
    def __init__(self) -> None:
        self._transports: dict[str, TransportSpec] = {}

    def register(self, spec: TransportSpec) -> None:
        self._transports[spec.transport_id] = spec
        logger.debug("Registered transport: %s", spec.transport_id)

    def get(self, transport_id: str) -> TransportSpec | None:
        return self._transports.get(transport_id)

    def all_transports(self) -> list[TransportSpec]:
        return list(self._transports.values())


TRANSPORT_REGISTRY = TransportRegistry()


def _register_builtins() -> None:
    from app.services.runtime.transport.agent_transport import agent_transport
    from app.services.runtime.transport.channel_transport import channel_transport

    TRANSPORT_REGISTRY.register(TransportSpec(
        transport_id="agent",
        adapter=agent_transport,
        description="Agent-side transport via RuntimeAdapter (SSE/HTTP to agent runtime).",
    ))
    TRANSPORT_REGISTRY.register(TransportSpec(
        transport_id="channel",
        adapter=channel_transport,
        description="Human-side transport via ChannelAdapter (Feishu, SSE, etc.).",
    ))


_register_builtins()
