"""Shared Feishu config normalization helpers."""

from __future__ import annotations

import copy
import json
from collections.abc import MutableMapping

_ALLOWLIST_KEYS = ("allowFrom", "groupAllowFrom", "groupSenderAllowFrom")
_LEGACY_KEYS = {"chatId", "chat_id", "reactEmoji", "replyToMessage"}


def _coerce_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return default


def _coerce_allowlist(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if item not in (None, "")]
    if isinstance(value, tuple | set):
        return [item for item in value if item not in (None, "")]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text[:1] in {"[", "{"}:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                pass
            else:
                if isinstance(parsed, list):
                    return [item for item in parsed if item not in (None, "")]
                if parsed not in (None, ""):
                    return [parsed]
        if "," in text:
            return [item.strip() for item in text.split(",") if item.strip()]
        return [text]
    if isinstance(value, (int, float)):
        return [value]
    return [value]


def _normalize_channel_block(channel: MutableMapping[str, object]) -> None:
    for legacy_key in _LEGACY_KEYS:
        channel.pop(legacy_key, None)

    if channel.get("groupPolicy") == "mention":
        channel["groupPolicy"] = "open"
        channel["requireMention"] = True

    channel["streaming"] = True
    channel["blockStreaming"] = False

    dm_policy = channel.get("dmPolicy")
    if "allowFrom" in channel:
        channel["allowFrom"] = _coerce_allowlist(channel.get("allowFrom"))
    elif dm_policy == "open":
        channel["allowFrom"] = ["*"]

    group_policy = channel.get("groupPolicy")
    if "groupAllowFrom" in channel:
        channel["groupAllowFrom"] = _coerce_allowlist(channel.get("groupAllowFrom"))
    elif group_policy == "open":
        channel["groupAllowFrom"] = ["*"]

    if "groupSenderAllowFrom" in channel:
        channel["groupSenderAllowFrom"] = _coerce_allowlist(channel.get("groupSenderAllowFrom"))

    groups = channel.get("groups")
    if isinstance(groups, dict):
        for group_cfg in groups.values():
            if not isinstance(group_cfg, MutableMapping):
                continue
            for legacy_key in _LEGACY_KEYS:
                group_cfg.pop(legacy_key, None)
            if group_cfg.get("groupPolicy") == "mention":
                group_cfg["groupPolicy"] = "open"
                group_cfg["requireMention"] = True
            if "allowFrom" in group_cfg:
                group_cfg["allowFrom"] = _coerce_allowlist(group_cfg.get("allowFrom"))


def normalize_openclaw_feishu_config(config: dict) -> dict:
    """Normalize Feishu config blocks in a full openclaw.json payload."""
    out = copy.deepcopy(config)
    channels = out.get("channels")
    if not isinstance(channels, dict):
        return out

    feishu = channels.get("feishu")
    if isinstance(feishu, MutableMapping):
        _normalize_channel_block(feishu)

        accounts = feishu.get("accounts")
        if isinstance(accounts, dict):
            default_account = feishu.get("defaultAccount")
            if isinstance(default_account, str):
                account_cfg = accounts.get(default_account)
                if isinstance(account_cfg, MutableMapping):
                    _normalize_channel_block(account_cfg)
            for account_cfg in accounts.values():
                if isinstance(account_cfg, MutableMapping):
                    _normalize_channel_block(account_cfg)

    return out
