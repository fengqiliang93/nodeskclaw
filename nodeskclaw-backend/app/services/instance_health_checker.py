"""Instance health checker: periodic background task that probes running instances."""

import asyncio
import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.instance import Instance, InstanceStatus
from app.services.runtime.compute.base import ComputeHandle

logger = logging.getLogger(__name__)

INSTANCE_HEALTH_CHECK_INTERVAL = 60  # seconds


class InstanceHealthChecker:
    """Background task: probes all running instances every INSTANCE_HEALTH_CHECK_INTERVAL seconds.

    Delegates health checking to each instance's ComputeProvider via COMPUTE_REGISTRY,
    so adding a new provider automatically enables health checking with zero code changes here.
    """

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

            for inst in instances:
                await self._check_instance(inst, db)

            await db.commit()

    async def _check_instance(self, instance: Instance, db):
        from app.services.runtime.registries.compute_registry import COMPUTE_REGISTRY

        spec = COMPUTE_REGISTRY.get(instance.compute_provider)
        if not spec or not spec.provider:
            return

        handle = self._build_handle(instance)
        try:
            probe = await spec.provider.health_check(handle)
            new_health = self._probe_to_health(probe)
            if new_health == "unhealthy":
                from app.services.instance_service import _in_deploy_grace
                if await _in_deploy_grace(instance.id, db):
                    new_health = "unknown"
            self._update_if_changed(instance, new_health)
        except Exception as e:
            logger.warning(
                "实例 %s (%s) 健康检查失败: %s",
                instance.name, instance.compute_provider, e,
            )

    @staticmethod
    def _build_handle(instance: Instance) -> ComputeHandle:
        advanced = json.loads(instance.advanced_config) if instance.advanced_config else {}
        return ComputeHandle(
            provider=instance.compute_provider,
            instance_id=instance.id,
            namespace=instance.namespace or "",
            endpoint=instance.ingress_domain or "",
            status=instance.status,
            extra={
                "slug": instance.slug,
                "runtime": instance.runtime,
                "compose_path": advanced.get("compose_path", ""),
                "cluster_id": instance.cluster_id,
            },
        )

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
