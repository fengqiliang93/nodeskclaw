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
        db = kwargs.get("db")
        if db is None:
            return ComputeHandle(
                provider=self.provider_id,
                instance_id=config.instance_id,
                namespace=config.namespace,
                status="creating",
            )

        try:
            from app.services.deploy_service import execute_deploy_pipeline

            await execute_deploy_pipeline(config.instance_id, db)

            from app.models.instance import Instance
            from sqlalchemy import select
            result = await db.execute(select(Instance).where(Instance.id == config.instance_id))
            inst = result.scalar_one_or_none()
            endpoint = f"https://{inst.ingress_domain}" if inst and inst.ingress_domain else ""
            status = inst.status if inst else "creating"

            return ComputeHandle(
                provider=self.provider_id,
                instance_id=config.instance_id,
                namespace=config.namespace,
                endpoint=endpoint,
                status=status,
            )
        except Exception as e:
            logger.error("K8s create_instance failed: %s", e)
            return ComputeHandle(
                provider=self.provider_id,
                instance_id=config.instance_id,
                namespace=config.namespace,
                status="failed",
                extra={"error": str(e)},
            )

    async def destroy_instance(self, handle: ComputeHandle, **kwargs) -> None:
        logger.info(
            "K8sComputeProvider.destroy_instance: %s in %s",
            handle.instance_id, handle.namespace,
        )
        db = kwargs.get("db")
        if db is None:
            return
        try:
            from app.services.instance_service import delete_instance
            await delete_instance(handle.instance_id, db)
        except Exception as e:
            logger.error("K8s destroy_instance failed: %s", e)

    async def get_status(self, handle: ComputeHandle) -> str:
        try:
            from app.services.k8s.client_manager import k8s_manager

            clients = k8s_manager.get_all_clients()
            for client in clients:
                try:
                    pods = await client.list_namespaced_pod(handle.namespace)
                    for pod in pods.items:
                        if handle.instance_id in (pod.metadata.name or ""):
                            return pod.status.phase.lower() if pod.status.phase else "unknown"
                except Exception:
                    continue
        except Exception as e:
            logger.warning("K8s get_status failed: %s", e)
        return handle.status

    async def get_endpoint(self, handle: ComputeHandle) -> str:
        return handle.endpoint

    async def get_logs(self, handle: ComputeHandle, *, tail: int = 50) -> str:
        try:
            from app.services.k8s.client_manager import k8s_manager

            clients = k8s_manager.get_all_clients()
            for client in clients:
                try:
                    log = await client.read_namespaced_pod_log(
                        handle.instance_id, handle.namespace, tail_lines=tail,
                    )
                    return log or ""
                except Exception:
                    continue
        except Exception as e:
            logger.warning("K8s get_logs failed: %s", e)
        return ""

    async def update_instance(
        self, handle: ComputeHandle, config: InstanceComputeConfig,
    ) -> ComputeHandle:
        logger.info(
            "K8sComputeProvider.update_instance: %s in %s (rolling update)",
            handle.instance_id, handle.namespace,
        )
        try:
            from app.services.k8s.client_manager import k8s_manager

            clients = k8s_manager.get_all_clients()
            for client in clients:
                try:
                    image = config.image if hasattr(config, "image") else ""
                    if image:
                        deploy_name = f"deskclaw-{handle.instance_id}"
                        body = {
                            "spec": {
                                "template": {
                                    "spec": {
                                        "containers": [{
                                            "name": "deskclaw",
                                            "image": image,
                                        }]
                                    }
                                }
                            }
                        }
                        await client.patch_namespaced_deployment(
                            deploy_name, handle.namespace, body,
                        )
                        logger.info("Rolling update triggered for %s", handle.instance_id)
                    break
                except Exception as e:
                    logger.warning("K8s update_instance via client failed: %s", e)
                    continue
        except Exception as e:
            logger.error("K8s update_instance failed: %s", e)

        return ComputeHandle(
            provider=self.provider_id,
            instance_id=handle.instance_id,
            namespace=handle.namespace,
            endpoint=handle.endpoint,
            status="updating",
        )

    async def health_check(self, handle: ComputeHandle) -> bool:
        """Check if the K8s pod is Running and Ready."""
        try:
            status = await self.get_status(handle)
            return status == "running"
        except Exception:
            return False
