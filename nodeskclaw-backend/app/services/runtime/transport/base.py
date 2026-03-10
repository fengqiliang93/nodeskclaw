"""TransportAdapter — protocol for delivering messages to target nodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.services.runtime.messaging.envelope import MessageEnvelope


@dataclass
class DeliveryResult:
    success: bool
    target_node_id: str
    transport: str = ""
    latency_ms: int = 0
    error: str = ""
    extra: dict = field(default_factory=dict)


class TransportAdapter(Protocol):
    async def deliver(
        self,
        envelope: MessageEnvelope,
        target_node_id: str,
        *,
        workspace_id: str = "",
    ) -> DeliveryResult: ...

    async def health_check(self, target_node_id: str) -> bool: ...
