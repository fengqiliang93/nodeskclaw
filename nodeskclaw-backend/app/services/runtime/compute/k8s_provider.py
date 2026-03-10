"""K8sComputeProvider — manages agent instances as Kubernetes Deployments."""

from __future__ import annotations

import logging

from app.services.runtime.compute.base import (
    ComputeHandle,
    InstanceComputeConfig,
)

logger = logging.getLogger(__name__)


class K8sComputeProvider:
    """Kubernetes-based compute provider.

    Delegates to the existing DeploymentAdapter (CE/EE) for K8s-specific
    differences (namespace naming, Ingress proxy, NetworkPolicy, etc.).
    """

    provider_id = "k8s"

    async def create_instance(
        self, config: InstanceComputeConfig, **kwargs,
    ) -> ComputeHandle:
        logger.info(
            "K8sComputeProvider.create_instance: %s in %s",
            config.instance_id, config.namespace,
        )
        return ComputeHandle(
            provider=self.provider_id,
            instance_id=config.instance_id,
            namespace=config.namespace,
            status="creating",
        )

    async def destroy_instance(self, handle: ComputeHandle) -> None:
        logger.info(
            "K8sComputeProvider.destroy_instance: %s in %s",
            handle.instance_id, handle.namespace,
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
            "K8sComputeProvider.update_instance: %s in %s",
            handle.instance_id, handle.namespace,
        )
        return handle
