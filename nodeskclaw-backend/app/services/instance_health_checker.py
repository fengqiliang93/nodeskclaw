"""Instance health checker: periodic background task that probes running instances."""

import asyncio
import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.cluster import Cluster
from app.models.instance import Instance, InstanceStatus

logger = logging.getLogger(__name__)

INSTANCE_HEALTH_CHECK_INTERVAL = 60  # seconds


class InstanceHealthChecker:
    """Background task: probes all running instances every INSTANCE_HEALTH_CHECK_INTERVAL seconds."""

    def __init__(self, session_factory: async_sessionmaker):
        self._session_factory = session_factory
        self._task: asyncio.Task | None = None

    def start(self):
        self._task = asyncio.create_task(self._loop())
        logger.info("实例健康巡检已启动 (间隔 %ds)", INSTANCE_HEALTH_CHECK_INTERVAL)

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("实例健康巡检已停止")

    async def _loop(self):
        await asyncio.sleep(15)
        while True:
            try:
                await self._check_all()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("实例健康巡检异常")
            await asyncio.sleep(INSTANCE_HEALTH_CHECK_INTERVAL)

    async def _check_all(self):
        async with self._session_factory() as db:
            result = await db.execute(
                select(Instance).where(
                    Instance.status == InstanceStatus.running,
                    Instance.deleted_at.is_(None),
                )
            )
            instances = result.scalars().all()
            if not instances:
                return

            docker_instances = [i for i in instances if i.compute_provider == "docker"]
            k8s_instances = [i for i in instances if i.compute_provider == "k8s"]

            for inst in docker_instances:
                await self._check_docker(inst, db)

            if k8s_instances:
                await self._check_k8s_batch(k8s_instances, db)

            await db.commit()

    async def _check_docker(self, instance: Instance, db):
        from app.services.runtime.compute.base import ComputeHandle
        from app.services.runtime.compute.docker_provider import DockerComputeProvider

        advanced = json.loads(instance.advanced_config) if instance.advanced_config else {}
        handle = ComputeHandle(
            provider="docker",
            instance_id=instance.id,
            namespace=instance.namespace,
            endpoint=instance.ingress_domain or "",
            status=instance.status,
            extra={"compose_path": advanced.get("compose_path", ""), "slug": instance.slug, "runtime": instance.runtime},
        )
        try:
            provider = DockerComputeProvider()
            probe = await provider.health_check(handle)
            new_status = self._probe_to_health(probe)
            if new_status == "unhealthy":
                from app.services.instance_service import _in_deploy_grace
                if await _in_deploy_grace(instance.id, db):
                    new_status = "unknown"
            self._update_if_changed(instance, new_status)
        except Exception as e:
            logger.warning("Docker 实例 %s 健康检查失败: %s", instance.name, e)

    async def _check_k8s_batch(self, instances: list[Instance], db):
        cluster_groups: dict[str, list[Instance]] = {}
        for inst in instances:
            cluster_groups.setdefault(inst.cluster_id, []).append(inst)

        for cluster_id, group in cluster_groups.items():
            cluster_result = await db.execute(
                select(Cluster).where(Cluster.id == cluster_id, Cluster.deleted_at.is_(None))
            )
            cluster = cluster_result.scalar_one_or_none()
            if not cluster or not cluster.credentials_encrypted:
                continue

            try:
                from app.services.runtime.registries.compute_registry import require_k8s_client
                k8s = await require_k8s_client(cluster)

                for inst in group:
                    slug = inst.slug or inst.name
                    label_selector = f"app.kubernetes.io/name={slug}"
                    try:
                        pods = await k8s.list_pods(inst.namespace, label_selector)
                        if not pods:
                            new_health = "unknown"
                        else:
                            all_ready = all(
                                all(c.get("ready", False) for c in p.get("containers", []))
                                and len(p.get("containers", [])) > 0
                                for p in pods
                            )
                            new_health = "healthy" if all_ready else "unhealthy"
                        self._update_if_changed(inst, new_health)
                    except Exception as e:
                        logger.warning("K8s 实例 %s 健康检查失败: %s", inst.name, e)
            except Exception as e:
                logger.warning("集群 %s K8s 连接失败，跳过该集群实例健康检查: %s", cluster_id, e)

    @staticmethod
    def _probe_to_health(probe: dict) -> str:
        if probe["healthy"] is True:
            return "healthy"
        if probe["healthy"] is False:
            return "unhealthy"
        return "unknown"

    @staticmethod
    def _update_if_changed(instance: Instance, new_health: str):
        if instance.health_status != new_health:
            old = instance.health_status
            instance.health_status = new_health
            logger.info(
                "实例 %s 健康状态变更: %s -> %s",
                instance.name, old, new_health,
            )
