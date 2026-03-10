"""TransportRegistry — maps transport identifiers to transport adapter factories."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TransportSpec:
    transport_id: str
    description: str | None = None
    config_schema: dict | None = None


class TransportRegistry:
    def __init__(self) -> None:
        self._transports: dict[str, TransportSpec] = {}
        self._factories: dict[str, Any] = {}

    def register(self, spec: TransportSpec, factory: Any = None) -> None:
        self._transports[spec.transport_id] = spec
        if factory is not None:
            self._factories[spec.transport_id] = factory
        logger.debug("Registered transport: %s", spec.transport_id)

    def get(self, transport_id: str) -> TransportSpec | None:
        return self._transports.get(transport_id)

    def get_factory(self, transport_id: str) -> Any | None:
        return self._factories.get(transport_id)

    def all_transports(self) -> list[TransportSpec]:
        return list(self._transports.values())


TRANSPORT_REGISTRY = TransportRegistry()

TRANSPORT_REGISTRY.register(TransportSpec(
    transport_id="agent",
    description="Agent-side transport via RuntimeAdapter (SSE/HTTP to agent runtime).",
))

TRANSPORT_REGISTRY.register(TransportSpec(
    transport_id="channel",
    description="Human-side transport via ChannelAdapter (Feishu, SSE, etc.).",
))
