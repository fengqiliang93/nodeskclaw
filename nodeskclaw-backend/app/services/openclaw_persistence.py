"""Helpers for persisting OpenClaw runtime config snapshots."""

from __future__ import annotations

import copy
import json
from pathlib import Path

PERSISTENT_CONFIG_SNAPSHOT_REL = Path(".openclaw") / "persistent-config.snapshot.json"


def build_persistent_config_snapshot(config: dict) -> dict:
    """Build a durable snapshot from the current OpenClaw config."""
    snapshot = copy.deepcopy(config)
    if isinstance(snapshot, dict):
        snapshot.pop("plugins", None)
    return snapshot


async def write_persistent_config_snapshot(fs, config: dict) -> None:
    """Write the durable snapshot alongside openclaw.json."""
    snapshot = build_persistent_config_snapshot(config)
    await fs.mkdir(str(PERSISTENT_CONFIG_SNAPSHOT_REL.parent))
    await fs.write_text(
        str(PERSISTENT_CONFIG_SNAPSHOT_REL),
        json.dumps(snapshot, indent=2, ensure_ascii=False),
    )
