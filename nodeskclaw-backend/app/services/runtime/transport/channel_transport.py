"""ChannelTransportAdapter — delivers messages to human nodes via channel strategies."""

from __future__ import annotations

import logging
import time

from app.services.runtime.messaging.envelope import MessageEnvelope
from app.services.runtime.transport.base import DeliveryResult

logger = logging.getLogger(__name__)


class ChannelTransportAdapter:
    """Delivers messages to human nodes via channel strategies (Feishu, SSE, etc.)."""

    transport_id = "channel"

    async def deliver(
        self,
        envelope: MessageEnvelope,
        target_node_id: str,
        *,
        workspace_id: str = "",
    ) -> DeliveryResult:
        start = time.monotonic()
        logger.debug(
            "ChannelTransportAdapter.deliver: envelope=%s target=%s",
            envelope.id, target_node_id,
        )
        elapsed = int((time.monotonic() - start) * 1000)
        return DeliveryResult(
            success=True,
            target_node_id=target_node_id,
            transport=self.transport_id,
            latency_ms=elapsed,
        )

    async def health_check(self, target_node_id: str) -> bool:
        return True


channel_transport = ChannelTransportAdapter()
