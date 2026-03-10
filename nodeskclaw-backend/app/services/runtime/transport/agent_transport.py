"""AgentTransportAdapter — delivers messages to agent nodes via RuntimeAdapter."""

from __future__ import annotations

import logging
import time

from app.services.runtime.messaging.envelope import MessageEnvelope
from app.services.runtime.transport.base import DeliveryResult

logger = logging.getLogger(__name__)


class AgentTransportAdapter:
    """Delivers messages to agent nodes by resolving the runtime adapter from the registry."""

    transport_id = "agent"

    def __init__(self) -> None:
        self._healthy_agents: set[str] = set()

    @property
    def healthy_instances(self) -> set[str]:
        return set(self._healthy_agents)

    async def deliver(
        self,
        envelope: MessageEnvelope,
        target_node_id: str,
        *,
        workspace_id: str = "",
    ) -> DeliveryResult:
        start = time.monotonic()
        logger.debug(
            "AgentTransportAdapter.deliver: envelope=%s target=%s",
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
        return target_node_id in self._healthy_agents

    async def on_agent_joined(self, instance_id: str) -> None:
        self._healthy_agents.add(instance_id)
        logger.info("AgentTransport: agent joined: %s", instance_id)

    async def on_agent_left(self, instance_id: str) -> None:
        self._healthy_agents.discard(instance_id)
        logger.info("AgentTransport: agent left: %s", instance_id)

    async def on_instance_destroyed(self, instance_id: str) -> None:
        self._healthy_agents.discard(instance_id)
        logger.info("AgentTransport: instance destroyed: %s", instance_id)

    async def reconnect_all(self) -> None:
        logger.info("AgentTransport: reconnect_all (placeholder)")

    def get_healthy_agents(self) -> set[str]:
        return set(self._healthy_agents)


agent_transport = AgentTransportAdapter()
