"""Startup reconcile for OpenClaw runtime defaults.

Ensures legacy instances keep stable defaults after backend/image upgrades:
- tools.allow full default (without touching gateway token / runtime data)
- exec security defaults
- Feishu streaming defaults + legacy policy normalization
"""

from __future__ import annotations

import copy
import logging
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.services.feishu_config import normalize_openclaw_feishu_config
from app.services.openclaw_persistence import write_persistent_config_snapshot
from app.utils.jsonc import (
    DEFAULT_SEARXNG_BASE_URL,
    ensure_agent_defaults,
    ensure_browser_no_sandbox,
    ensure_channel_plugin_integrity,
    ensure_exec_security,
    ensure_nodeskclaw_tool_allow,
    ensure_searxng_web_search,
    ensure_tools_allow_full_default,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = {"running", "learning", "restarting", "updating", "rebuilding", "restoring"}


async def reconcile_openclaw_runtime_defaults(
    session_factory: "async_sessionmaker[AsyncSession]",
) -> None:
    try:
        await _do_reconcile(session_factory)
    except Exception:
        logger.warning("openclaw config reconcile: 启动修复失败", exc_info=True)


async def _do_reconcile(
    session_factory: "async_sessionmaker[AsyncSession]",
) -> None:
    from app.models.instance import Instance
    from app.services.nfs_mount import remote_fs
    from app.services.runtime.config_adapter import get_config_adapter

    updated = 0
    skipped = 0
    failed = 0

    async with session_factory() as db:
        result = await db.execute(
            select(Instance).where(
                Instance.runtime == "openclaw",
                Instance.deleted_at.is_(None),
                Instance.status.in_(_ACTIVE_STATUSES),
            )
        )
        instances = list(result.scalars().all())

        for inst in instances:
            try:
                adapter = get_config_adapter(inst.runtime or "openclaw")
                async with remote_fs(inst, db) as fs:
                    config = await adapter.read_config(fs)
                    if not isinstance(config, dict):
                        skipped += 1
                        continue

                    before = copy.deepcopy(config)
                    after = normalize_openclaw_feishu_config(config)
                    ensure_tools_allow_full_default(after)
                    ensure_nodeskclaw_tool_allow(after)
                    ensure_exec_security(after)
                    ensure_browser_no_sandbox(after)
                    ensure_agent_defaults(after)
                    ensure_searxng_web_search(after, DEFAULT_SEARXNG_BASE_URL)
                    ensure_channel_plugin_integrity(after)

                    if after == before:
                        skipped += 1
                        continue

                    await adapter.write_config(fs, after)
                    await write_persistent_config_snapshot(fs, after)
                    updated += 1
            except Exception as exc:
                failed += 1
                logger.warning(
                    "openclaw config reconcile: 实例 %s 修复失败: %s",
                    inst.name,
                    exc,
                )

    logger.info(
        "openclaw config reconcile: updated=%d skipped=%d failed=%d",
        updated,
        skipped,
        failed,
    )
