"""DockerComputeProvider — manages agent instances as Docker Compose services."""

from __future__ import annotations

import logging

from app.services.runtime.compute.base import (
    ComputeHandle,
    InstanceComputeConfig,
)

logger = logging.getLogger(__name__)


class DockerComputeProvider:
    """Docker compose-based compute provider for local/dev agent instances."""

    provider_id = "docker"

    async def create_instance(
        self, config: InstanceComputeConfig, **kwargs,
    ) -> ComputeHandle:
        logger.info(
            "DockerComputeProvider.create_instance: %s",
            config.instance_id,
        )
        return ComputeHandle(
            provider=self.provider_id,
            instance_id=config.instance_id,
            namespace="docker-local",
            endpoint=f"http://{config.slug}:3000",
            status="creating",
        )

    async def destroy_instance(self, handle: ComputeHandle) -> None:
        logger.info(
            "DockerComputeProvider.destroy_instance: %s",
            handle.instance_id,
        )

    async def get_status(self, handle: ComputeHandle) -> str:
        return handle.status

    async def get_endpoint(self, handle: ComputeHandle) -> str:
        return handle.endpoint

    async def get_logs(self, handle: ComputeHandle, *, tail: int = 50) -> str:
        return ""

    async def update_instance(
        self, handle: ComputeHandle, config: InstanceComputeConfig,
    ) -> ComputeHandle:
        logger.info(
            "DockerComputeProvider.update_instance: %s",
            handle.instance_id,
        )
        return handle
