"""启动时修复已有飞书实例的节点选择器。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings

if TYPE_CHECKING:
    from app.models.instance import Instance

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = {"running", "learning", "restarting", "updating", "rebuilding", "restoring"}


async def reconcile_feishu_instances(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if not settings.FEISHU_NODE_SELECTOR.strip():
        logger.info("feishu reconcile: FEISHU_NODE_SELECTOR 未配置，跳过")
        return
    try:
        await _do_reconcile(session_factory)
    except Exception:
        logger.warning("feishu reconcile: 启动修复失败", exc_info=True)


async def _do_reconcile(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from app.models.cluster import Cluster
    from app.models.instance import Instance
    from app.services.channel_config_service import (
        _apply_feishu_node_selector,
        _clear_incompatible_node_selector,
        _has_incompatible_local_pvc,
        _parse_node_selector,
        has_openclaw_feishu_channel,
    )
    from app.services.nfs_mount import remote_fs
    from app.services.runtime.registries.compute_registry import require_k8s_client
    from app.services.runtime.config_adapter import get_config_adapter

    desired_selector = _parse_node_selector(settings.FEISHU_NODE_SELECTOR)

    async with session_factory() as db:
        result = await db.execute(
            select(Instance, Cluster)
            .join(Cluster, Instance.cluster_id == Cluster.id)
            .where(
                Instance.compute_provider == "k8s",
                Instance.runtime == "openclaw",
                Instance.deleted_at.is_(None),
                Instance.status.in_(_ACTIVE_STATUSES),
                Cluster.deleted_at.is_(None),
            )
        )
        pairs = list(result.all())

        if not pairs:
            logger.info("feishu reconcile: 无活跃 OpenClaw 实例")
            return

        repaired = 0
        skipped = 0
        failed = 0
        restored = 0
        k8s_clients: dict[str, object] = {}
        node_labels: dict[tuple[str, str], dict[str, str]] = {}

        for inst, cluster in pairs:
            try:
                adapter = get_config_adapter(inst.runtime or "openclaw")
                async with remote_fs(inst, db) as fs:
                    config = await adapter.read_config(fs)
                if not has_openclaw_feishu_channel(config):
                    skipped += 1
                    continue
                k8s = k8s_clients.get(cluster.id)
                if k8s is None:
                    k8s = await require_k8s_client(cluster)
                    k8s_clients[cluster.id] = k8s
                if await _has_incompatible_local_pvc(
                    cluster.id,
                    inst,
                    desired_selector,
                    k8s,
                    node_labels,
                ):
                    await _clear_incompatible_node_selector(inst, db, desired_selector, k8s)
                    restored += 1
                    continue
                await _apply_feishu_node_selector(inst, db)
                repaired += 1
            except Exception as exc:
                failed += 1
                logger.warning(
                    "feishu reconcile: 实例 %s 修复失败: %s",
                    inst.name,
                    exc,
                )

    logger.info(
        "feishu reconcile: repaired=%d restored=%d skipped=%d failed=%d",
        repaired,
        restored,
        skipped,
        failed,
    )
