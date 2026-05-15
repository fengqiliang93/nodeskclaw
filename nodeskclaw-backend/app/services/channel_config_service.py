"""Channel config service: discover, read/write channel configs (runtime-aware)."""

import asyncio
import copy
import json
import logging
import textwrap
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException, BadRequestError
from app.models.cluster import Cluster
from app.models.instance import Instance
from app.services.feishu_config import normalize_openclaw_feishu_config
from app.services.nfs_mount import remote_fs
from app.services.openclaw_persistence import write_persistent_config_snapshot
from app.services.runtime.config_adapter import get_config_adapter
from app.services.unified_channel_schema import (
    UNIFIED_CHANNEL_REGISTRY,
    get_legacy_channel_schemas,
)

logger = logging.getLogger(__name__)

SYSTEM_CHANNEL_IDS = {"nodeskclaw", "learning"}

OPENCLAW_FEISHU_PLATFORM_DEFAULTS: dict[str, object] = {
    "connectionMode": "websocket",
    "streaming": True,
    "blockStreaming": False,
}


CHANNEL_LABELS: dict[str, str] = {
    "feishu": "Feishu / 飞书",
    "dingtalk": "DingTalk / 钉钉",
    "slack": "Slack",
    "telegram": "Telegram",
    "discord": "Discord",
    "whatsapp": "WhatsApp",
    "irc": "IRC",
    "signal": "Signal",
    "googlechat": "Google Chat",
    "msteams": "Microsoft Teams",
    "matrix": "Matrix",
    "line": "LINE",
    "mattermost": "Mattermost",
    "bluebubbles": "BlueBubbles",
    "nextcloud-talk": "Nextcloud Talk",
    "synology-chat": "Synology Chat",
    "nostr": "Nostr",
    "tlon": "Tlon",
    "twitch": "Twitch",
    "imessage": "iMessage",
    "zalo": "Zalo",
    "zalouser": "Zalo Personal",
}

CHANNEL_ORDER: dict[str, int] = {
    "feishu": 35,
    "dingtalk": 36,
    "slack": 40,
    "telegram": 45,
    "discord": 50,
    "googlechat": 55,
    "nostr": 55,
    "msteams": 60,
    "mattermost": 65,
    "nextcloud-talk": 65,
    "matrix": 70,
    "bluebubbles": 75,
    "line": 75,
    "zalo": 80,
    "zalouser": 85,
    "synology-chat": 90,
    "tlon": 90,
    "whatsapp": 95,
    "irc": 95,
    "signal": 95,
    "imessage": 95,
    "twitch": 95,
}


# Backward-compatible CHANNEL_SCHEMAS generated from UNIFIED_CHANNEL_REGISTRY
CHANNEL_SCHEMAS: dict[str, list[dict]] = get_legacy_channel_schemas()

SENSITIVE_KEYS = {
    "appSecret", "botToken", "appToken", "token", "appPassword",
    "accessToken", "encryptKey", "verificationToken", "apiKey",
    "serviceAccountKeyFile", "clientSecret",
    "app_secret", "bot_token", "app_token", "client_secret",
    "encrypt_key", "verification_token",
}


# ── Repo Channel Plugins ─────────────────────────────────

REPO_CHANNEL_PLUGINS: dict[str, dict] = {}


def _discover_repo_channel_plugins() -> None:
    """Scan project repo for deployable channel plugins (dirs matching openclaw-channel-*)."""
    global REPO_CHANNEL_PLUGINS  # noqa: PLW0603
    candidates = [
        Path(__file__).resolve().parents[3],
        Path("/app"),
    ]
    for root in candidates:
        if not root.exists():
            continue
        for d in sorted(root.iterdir()):
            if not d.name.startswith("openclaw-channel-"):
                continue
            if not (d / "index.ts").exists():
                continue
            plugin_json = d / "openclaw.plugin.json"
            if not plugin_json.exists():
                continue
            try:
                meta = json.loads(plugin_json.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            channels = meta.get("channels", [])
            if not channels:
                continue
            channel_id = channels[0]
            if channel_id in SYSTEM_CHANNEL_IDS:
                continue
            files = _collect_plugin_files(d)
            if files:
                REPO_CHANNEL_PLUGINS[channel_id] = {
                    "dir_name": d.name,
                    "source_root": str(root),
                    "files": files,
                }
        if REPO_CHANNEL_PLUGINS:
            break


def _collect_plugin_files(plugin_dir: Path, prefix: str = "") -> list[str]:
    """Recursively collect relative file paths in a plugin directory."""
    result = []
    for item in sorted(plugin_dir.iterdir()):
        if item.name.startswith(".") or item.name == "node_modules":
            continue
        rel = f"{prefix}{item.name}" if not prefix else f"{prefix}/{item.name}"
        if item.is_file():
            result.append(rel)
        elif item.is_dir():
            result.extend(_collect_plugin_files(item, rel))
    return result


_discover_repo_channel_plugins()


# ── Discovery ─────────────────────────────────────────────

_DISCOVER_SCRIPT = textwrap.dedent("""\
    const path = require('path');
    const fs = require('fs');
    const result = [];
    function scan(dir, origin) {
      if (!fs.existsSync(dir)) return;
      for (const name of fs.readdirSync(dir)) {
        const pj = path.join(dir, name, 'openclaw.plugin.json');
        const pkj = path.join(dir, name, 'package.json');
        if (!fs.existsSync(pj)) continue;
        try {
          const plugin = JSON.parse(fs.readFileSync(pj, 'utf8'));
          if (!plugin.channels || !plugin.channels.length) continue;
          let pkg = {};
          try { pkg = JSON.parse(fs.readFileSync(pkj, 'utf8')); } catch(e) {}
          const ch = (pkg.openclaw || {}).channel || {};
          result.push({
            id: plugin.channels[0],
            pluginId: plugin.id || name,
            label: ch.label || ch.selectionLabel || plugin.id || name,
            description: pkg.description || '',
            origin: origin,
            order: ch.order || 999,
          });
        } catch(e) {}
      }
    }
    // Bundled extensions (OpenClaw is globally installed in the Pod)
    try {
      const globalRoot = require('child_process').execSync('npm root -g').toString().trim();
      scan(path.join(globalRoot, 'openclaw', 'extensions'), 'bundled');
    } catch(e) {}
    // Workspace extensions
    scan('/root/.openclaw/extensions', 'workspace');
    console.log(JSON.stringify(result));
""")


async def discover_available_channels(
    instance: Instance, db: AsyncSession,
) -> list[dict]:
    """Discover available channel plugins (runtime-aware).

    OpenClaw: Node.js exec scan of plugin directories.
    NanoBot: return static list from adapter.supported_channels().

    After collecting runtime-native channels, augment with UNIFIED_CHANNEL_REGISTRY
    entries to ensure a consistent view across all runtimes.
    """
    runtime = instance.runtime or "openclaw"
    adapter = get_config_adapter(runtime)

    if runtime == "openclaw":
        raw_channels = await _discover_openclaw_channels(instance, db)
    else:
        raw_channels = []
        for cid in adapter.supported_channels():
            if cid in SYSTEM_CHANNEL_IDS:
                continue
            defn = UNIFIED_CHANNEL_REGISTRY.get(cid)
            raw_channels.append({
                "id": cid,
                "label": defn.label if defn else CHANNEL_LABELS.get(cid, cid),
                "description": "",
                "origin": "builtin",
                "order": defn.order if defn else CHANNEL_ORDER.get(cid, 999),
                "has_schema": cid in UNIFIED_CHANNEL_REGISTRY or cid in CHANNEL_SCHEMAS,
            })

    seen_ids = {ch["id"] for ch in raw_channels}
    native_channels = set(adapter.supported_channels())

    for cid, defn in UNIFIED_CHANNEL_REGISTRY.items():
        if cid in seen_ids or cid in SYSTEM_CHANNEL_IDS:
            continue
        supported = runtime in defn.supported_runtimes
        raw_channels.append({
            "id": cid,
            "label": defn.label,
            "description": "",
            "origin": "builtin",
            "order": defn.order,
            "has_schema": True,
            "supported": supported,
        })

    for ch in raw_channels:
        if "supported" not in ch:
            ch["supported"] = ch["id"] in native_channels

    raw_channels.sort(key=lambda c: (c["order"], c["id"]))
    return raw_channels


async def _discover_openclaw_channels(
    instance: Instance, db: AsyncSession,
) -> list[dict]:
    """OpenClaw-specific: Node.js exec scan of plugin directories."""
    last_error: Exception | None = None
    for attempt in range(1, 4):
        async with remote_fs(instance, db) as fs:
            try:
                if instance.compute_provider == "docker":
                    from app.services.nfs_mount import DockerFS
                    assert isinstance(fs, DockerFS)
                    raw = await fs.exec_command(["node", "-e", _DISCOVER_SCRIPT])
                else:
                    raw = await fs._k8s.exec_in_pod(
                        fs._ns, fs._pod,
                        ["node", "-e", _DISCOVER_SCRIPT],
                        container=fs._container,
                    )
                break
            except Exception as e:
                last_error = e
                transient = "Invalid response status" in str(e)
                if transient and attempt < 3:
                    logger.warning(
                        "Channel discovery exec 重试 %s/3: instance=%s error=%s",
                        attempt, instance.name, e,
                    )
                    await asyncio.sleep(2)
                    continue
                logger.error("Channel discovery exec failed: %s", e)
                raise AppException(
                    code=50200,
                    message=f"Channel 发现失败: {e}",
                    status_code=502,
                    message_key="errors.channel.discovery_failed",
                ) from e
    else:
        assert last_error is not None
        raise last_error

    if not raw:
        return []

    try:
        items: list[dict] = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Channel discovery returned non-JSON: %s", raw[:200])
        return []

    channels = []
    for item in items:
        cid = item.get("id", "")
        if cid in SYSTEM_CHANNEL_IDS:
            continue
        channels.append({
            "id": cid,
            "label": CHANNEL_LABELS.get(cid, item.get("label", cid)),
            "description": item.get("description", ""),
            "origin": item.get("origin", "unknown"),
            "order": CHANNEL_ORDER.get(cid, item.get("order", 999)),
            "has_schema": cid in UNIFIED_CHANNEL_REGISTRY or cid in CHANNEL_SCHEMAS,
        })

    channels.sort(key=lambda c: (c["order"], c["id"]))

    return channels


# ── Config Read / Write ───────────────────────────────────

def _mask_sensitive(config: dict) -> dict:
    """Mask sensitive fields in channel config dict recursively for frontend display."""

    def _mask_value(value):
        if isinstance(value, dict):
            out = {}
            for key, item in value.items():
                if key in SENSITIVE_KEYS and isinstance(item, str) and len(item) > 4:
                    out[key] = item[:4] + "***" + item[-2:]
                else:
                    out[key] = _mask_value(item)
            return out
        if isinstance(value, list):
            return [_mask_value(item) for item in value]
        return value

    return _mask_value(config)


def _deep_merge_dict(base: dict, patch: dict) -> dict:
    """Deep-merge dicts with patch precedence."""
    merged = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _sync_openclaw_feishu_default_account(
    old_native: dict,
    new_native: dict,
) -> dict:
    """Keep OpenClaw Feishu multi-account config consistent when platform edits top-level fields."""
    merged = _deep_merge_dict(old_native, new_native)

    accounts = merged.get("accounts")
    if not isinstance(accounts, dict):
        accounts = {}

    default_account = merged.get("defaultAccount")
    if not accounts:
        default_account = "default"
    elif not isinstance(default_account, str) or not default_account:
        default_account = sorted(accounts.keys())[0]
    if not default_account:
        default_account = "default"

    account_cfg = accounts.get(default_account)
    if not isinstance(account_cfg, dict):
        account_cfg = {}

    # Keep effective runtime credentials aligned with what platform just wrote.
    mirror_keys = {
        "appId",
        "appSecret",
        "encryptKey",
        "verificationToken",
        "domain",
        "connectionMode",
        "webhookPath",
        "allowFrom",
        "groupAllowFrom",
        "groupSenderAllowFrom",
        "groupPolicy",
        "dmPolicy",
        "requireMention",
        "topicSessionMode",
        "streaming",
        "blockStreaming",
    }
    for key in mirror_keys:
        if key in new_native:
            account_cfg[key] = copy.deepcopy(new_native[key])

    if "allowFrom" not in account_cfg:
        account_cfg["allowFrom"] = copy.deepcopy(
            merged.get("allowFrom", [])
        )
    if "groupAllowFrom" not in account_cfg:
        account_cfg["groupAllowFrom"] = copy.deepcopy(
            merged.get("groupAllowFrom", [])
        )

    accounts[default_account] = account_cfg
    merged["accounts"] = accounts
    merged["defaultAccount"] = default_account
    return merged


def _apply_openclaw_feishu_platform_defaults(native_cfg: dict) -> dict:
    """Ensure OpenClaw receives explicit platform defaults for omitted Feishu policy fields."""
    out = copy.deepcopy(native_cfg)
    for key, value in OPENCLAW_FEISHU_PLATFORM_DEFAULTS.items():
        out.setdefault(key, value)
    out["streaming"] = True
    out["blockStreaming"] = False
    return out


def _parse_node_selector(raw: str) -> dict[str, str]:
    value = (raw or "").strip()
    if not value:
        return {}
    if value.startswith("{"):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise BadRequestError(
                message=f"FEISHU_NODE_SELECTOR JSON 解析失败: {exc}",
                message_key="errors.channel.invalid_feishu_node_selector",
            ) from exc
        if not isinstance(parsed, dict):
            raise BadRequestError(
                message="FEISHU_NODE_SELECTOR 必须是 JSON 对象",
                message_key="errors.channel.invalid_feishu_node_selector",
            )
        return {str(k): str(v) for k, v in parsed.items() if str(k).strip()}

    selector: dict[str, str] = {}
    for item in value.split(","):
        part = item.strip()
        if not part:
            continue
        if "=" not in part:
            raise BadRequestError(
                message=f"FEISHU_NODE_SELECTOR 格式非法: {part}",
                message_key="errors.channel.invalid_feishu_node_selector",
            )
        key, val = part.split("=", 1)
        key = key.strip()
        if not key:
            raise BadRequestError(
                message="FEISHU_NODE_SELECTOR 存在空 key",
                message_key="errors.channel.invalid_feishu_node_selector",
            )
        selector[key] = val.strip()
    return selector


def has_openclaw_feishu_channel(config: dict) -> bool:
    channels = config.get("channels")
    if not isinstance(channels, dict):
        return False
    feishu = channels.get("feishu")
    return isinstance(feishu, dict) and bool(feishu)


def _selector_matches_labels(selector: dict[str, str], labels: dict[str, str]) -> bool:
    return all(labels.get(key) == value for key, value in selector.items())


def _extract_pv_node_name(pv) -> str | None:
    affinity = getattr(getattr(pv, "spec", None), "node_affinity", None)
    required = getattr(affinity, "required", None)
    terms = getattr(required, "node_selector_terms", None) or []
    for term in terms:
        expressions = getattr(term, "match_expressions", None) or []
        for expression in expressions:
            if getattr(expression, "key", "") != "kubernetes.io/hostname":
                continue
            values = getattr(expression, "values", None) or []
            if values:
                return str(values[0])
    return None


async def _has_incompatible_local_pvc(
    cluster_id: str,
    instance: Instance,
    selector: dict[str, str],
    k8s,
    node_labels: dict[tuple[str, str], dict[str, str]] | None = None,
) -> bool:
    claim_name = f"{instance.slug or instance.name}-root-data"
    try:
        pvc = await k8s.core.read_namespaced_persistent_volume_claim(claim_name, instance.namespace)
    except Exception:
        return False

    volume_name = getattr(getattr(pvc, "spec", None), "volume_name", None)
    if not volume_name:
        return False

    pv = await k8s.core.read_persistent_volume(volume_name)
    node_name = _extract_pv_node_name(pv)
    if not node_name:
        return False

    cache_key = (cluster_id, node_name)
    labels = node_labels.get(cache_key) if node_labels is not None else None
    if labels is None:
        node = await k8s.core.read_node(node_name)
        labels = dict(getattr(getattr(node, "metadata", None), "labels", None) or {})
        if node_labels is not None:
            node_labels[cache_key] = labels
    return not _selector_matches_labels(selector, labels)


async def _clear_incompatible_node_selector(
    instance: Instance,
    db: AsyncSession,
    selector: dict[str, str],
    k8s,
) -> None:
    advanced = json.loads(instance.advanced_config) if instance.advanced_config else {}
    current = advanced.get("node_selector")
    if not isinstance(current, dict):
        current = {}
    next_selector = {
        key: value for key, value in current.items()
        if selector.get(key) != value
    }
    if next_selector:
        advanced["node_selector"] = next_selector
    else:
        advanced.pop("node_selector", None)
    instance.advanced_config = json.dumps(advanced, ensure_ascii=False) if advanced else None
    await db.commit()
    await db.refresh(instance)

    deploy_name = instance.slug or instance.name
    await k8s.apps.patch_namespaced_deployment(
        deploy_name,
        instance.namespace,
        {"spec": {"template": {"spec": {"nodeSelector": next_selector}}}},
    )
    logger.info(
        "实例 %s 的本地盘节点与目标 Feishu selector 冲突，已清理 selector",
        instance.name,
    )


async def _apply_feishu_node_selector(instance: Instance, db: AsyncSession) -> None:
    raw_selector = settings.FEISHU_NODE_SELECTOR
    selector = _parse_node_selector(raw_selector)
    if not selector:
        return

    advanced = json.loads(instance.advanced_config) if instance.advanced_config else {}
    current = advanced.get("node_selector")
    if not isinstance(current, dict):
        current = {}

    if instance.compute_provider == "k8s":
        cluster = (await db.execute(
            select(Cluster).where(
                Cluster.id == instance.cluster_id,
                Cluster.deleted_at.is_(None),
            )
        )).scalar_one_or_none()
        if cluster is not None:
            from app.services.runtime.registries.compute_registry import require_k8s_client
            k8s = await require_k8s_client(cluster)
            if await _has_incompatible_local_pvc(
                instance.cluster_id,
                instance,
                selector,
                k8s,
            ):
                await _clear_incompatible_node_selector(instance, db, selector, k8s)
                return

    merged_selector = {**current, **selector}
    if merged_selector != current:
        advanced["node_selector"] = merged_selector
        instance.advanced_config = json.dumps(advanced, ensure_ascii=False)
        await db.commit()
        await db.refresh(instance)

    if instance.compute_provider != "k8s":
        return

    cluster = (await db.execute(
        select(Cluster).where(
            Cluster.id == instance.cluster_id,
            Cluster.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if cluster is None:
        return

    from app.services.runtime.registries.compute_registry import require_k8s_client
    k8s = await require_k8s_client(cluster)
    deploy_name = instance.slug or instance.name
    await k8s.apps.patch_namespaced_deployment(
        deploy_name,
        instance.namespace,
        {"spec": {"template": {"spec": {"nodeSelector": merged_selector}}}},
    )
    logger.info(
        "已应用 Feishu 节点选择器: instance=%s selector=%s",
        instance.name,
        merged_selector,
    )


async def read_channel_configs(
    instance: Instance, db: AsyncSession,
) -> dict:
    """Read channels section from config file, excluding system channels (runtime-aware)."""
    runtime = instance.runtime or "openclaw"
    adapter = get_config_adapter(runtime)

    async with remote_fs(instance, db) as fs:
        try:
            config = await adapter.read_config(fs)
        except ValueError as e:
            logger.warning("读取配置文件失败 (runtime=%s): %s", runtime, e)
            raise AppException(
                code=50200,
                message=f"配置文件解析失败: {e}",
                status_code=502,
                message_key="errors.channel.config_read_failed",
            )

    if config is None:
        return {}

    all_channels: dict = adapter.extract_channels(config)
    user_channels = {}
    for cid, cfg in all_channels.items():
        if cid in SYSTEM_CHANNEL_IDS:
            continue
        if isinstance(cfg, dict):
            canonical = adapter.translate_from_runtime(cfg, cid)
            user_channels[cid] = _mask_sensitive(canonical)
        else:
            user_channels[cid] = cfg

    return user_channels


async def write_channel_configs(
    instance: Instance, db: AsyncSession, channel_configs: dict,
) -> dict:
    """Write user channel configs and restart instance (runtime-aware).

    Preserves system channel configs and other non-channel sections.
    """
    runtime = instance.runtime or "openclaw"
    adapter = get_config_adapter(runtime)

    async with remote_fs(instance, db) as fs:
        try:
            config = await adapter.read_config(fs)
        except ValueError as e:
            raise AppException(
                code=50200,
                message=f"配置文件解析失败: {e}",
                status_code=502,
                message_key="errors.channel.config_read_failed",
            )

        if config is None:
            config = {}

        existing_channels = adapter.extract_channels(config)

        for cid, new_cfg in channel_configs.items():
            if not isinstance(new_cfg, dict):
                continue
            old_native = existing_channels.get(cid)
            if isinstance(old_native, dict):
                old_canonical = adapter.translate_from_runtime(old_native, cid)
                for k, v in new_cfg.items():
                    if isinstance(v, str) and "***" in v and k in old_canonical:
                        new_cfg[k] = old_canonical[k]

        system_configs = {
            cid: cfg for cid, cfg in existing_channels.items()
            if cid in SYSTEM_CHANNEL_IDS
        }

        native_channels = {}
        for cid, cfg in channel_configs.items():
            if isinstance(cfg, dict):
                translated = adapter.translate_to_runtime(cfg, cid)
                if runtime == "openclaw" and cid == "feishu" and isinstance(translated, dict):
                    translated = _apply_openclaw_feishu_platform_defaults(translated)
                old_native = existing_channels.get(cid)
                if isinstance(old_native, dict) and isinstance(translated, dict):
                    if runtime == "openclaw" and cid == "feishu":
                        native_channels[cid] = _sync_openclaw_feishu_default_account(
                            old_native,
                            translated,
                        )
                    else:
                        native_channels[cid] = _deep_merge_dict(old_native, translated)
                else:
                    native_channels[cid] = translated
            else:
                native_channels[cid] = cfg

        merged = {**system_configs, **native_channels}
        config = adapter.merge_channels(config, merged)
        if runtime == "openclaw":
            config = normalize_openclaw_feishu_config(config)

        try:
            await adapter.write_config(fs, config)
            await write_persistent_config_snapshot(fs, config)
        except AppException:
            raise
        except Exception as e:
            logger.error("写入 Channel 配置失败: %s", e)
            raise AppException(
                code=50200, status_code=502,
                message="Channel 配置写入失败，实例可能正在重启中，请稍后重试",
                message_key="errors.channel.config_write_failed",
            )

    logger.info("已写入 Channel 配置: instance=%s runtime=%s channels=%s",
                instance.name, runtime, list(channel_configs.keys()))

    if runtime == "openclaw" and "feishu" in channel_configs:
        await _apply_feishu_node_selector(instance, db)

    result = await adapter.restart(instance, db)
    if runtime == "openclaw":
        from app.services.llm_config_service import ensure_openclaw_gateway_config

        await ensure_openclaw_gateway_config(instance, db)
    return result


# ── Custom Channel Deployment ─────────────────────────────

def _assert_openclaw_runtime(instance: Instance) -> None:
    runtime = instance.runtime or "openclaw"
    if runtime != "openclaw":
        raise BadRequestError(
            message=f"此操作仅支持 OpenClaw 引擎，当前引擎为 {runtime}",
            message_key="errors.channel.openclaw_only",
        )


async def deploy_repo_channel(
    instance: Instance, db: AsyncSession, channel_id: str,
) -> dict:
    """Deploy a repo-based channel plugin to the instance Pod (OpenClaw only)."""
    _assert_openclaw_runtime(instance)
    plugin_info = REPO_CHANNEL_PLUGINS.get(channel_id)
    if not plugin_info:
        raise BadRequestError(
            message=f"项目仓库中未找到 Channel: {channel_id}",
            message_key="errors.channel.repo_plugin_not_found",
        )

    source_root = Path(plugin_info["source_root"])
    dir_name = plugin_info["dir_name"]
    source_dir = source_root / dir_name

    if not source_dir.exists():
        raise BadRequestError(
            message=f"Channel 插件源目录不存在: {dir_name}",
            message_key="errors.channel.source_not_found",
        )

    adapter = get_config_adapter("openclaw")
    async with remote_fs(instance, db) as fs:
        target_base = f".openclaw/extensions/{dir_name}"
        for rel_path in plugin_info["files"]:
            src = source_dir / rel_path
            if not src.exists():
                continue
            parent = str(Path(f"{target_base}/{rel_path}").parent)
            if parent != target_base:
                await fs.mkdir(parent)
            await fs.write_text(
                f"{target_base}/{rel_path}",
                src.read_text(encoding="utf-8"),
            )

        config = await adapter.read_config(fs) or {}
        config.pop("plugins", None)
        await adapter.write_config(fs, config)

    logger.info("已部署仓库 Channel 插件: instance=%s channel=%s",
                instance.name, channel_id)
    return {"channel_id": channel_id, "status": "deployed"}


async def install_npm_channel(
    instance: Instance, db: AsyncSession, package_name: str,
) -> dict:
    """Install a third-party channel plugin via openclaw CLI in the Pod (OpenClaw only)."""
    _assert_openclaw_runtime(instance)
    if not package_name or not package_name.strip():
        raise BadRequestError(
            message="npm 包名不能为空",
            message_key="errors.channel.empty_package_name",
        )

    async with remote_fs(instance, db) as fs:
        try:
            if instance.compute_provider == "docker":
                from app.services.nfs_mount import DockerFS
                assert isinstance(fs, DockerFS)
                output = await fs.exec_command(
                    ["npx", "openclaw", "plugins", "install", package_name.strip()],
                )
            else:
                output = await fs._k8s.exec_in_pod(
                    fs._ns, fs._pod,
                    ["npx", "openclaw", "plugins", "install", package_name.strip()],
                    container=fs._container,
                )
        except Exception as e:
            logger.error("npm channel install failed: %s", e)
            raise AppException(
                code=50200,
                message=f"Channel 安装失败: {e}",
                status_code=502,
                message_key="errors.channel.install_failed",
            )

    logger.info("已安装 npm Channel: instance=%s package=%s",
                instance.name, package_name)
    return {"package": package_name, "status": "installed", "output": output}


async def upload_channel_plugin(
    instance: Instance, db: AsyncSession,
    plugin_files: dict[str, str],
    plugin_id: str,
) -> dict:
    """Deploy uploaded channel plugin files to the instance Pod (OpenClaw only).

    plugin_files: dict mapping relative paths to file contents (text).
    """
    _assert_openclaw_runtime(instance)
    if not plugin_id:
        raise BadRequestError(
            message="插件 ID 不能为空",
            message_key="errors.channel.empty_plugin_id",
        )

    adapter = get_config_adapter("openclaw")
    async with remote_fs(instance, db) as fs:
        target_base = f".openclaw/extensions/{plugin_id}"
        for rel_path, content in plugin_files.items():
            parent = str(Path(f"{target_base}/{rel_path}").parent)
            if parent != target_base:
                await fs.mkdir(parent)
            await fs.write_text(f"{target_base}/{rel_path}", content)

        config = await adapter.read_config(fs) or {}
        config.pop("plugins", None)
        await adapter.write_config(fs, config)

    logger.info("已部署上传 Channel 插件: instance=%s plugin=%s",
                instance.name, plugin_id)
    return {"plugin_id": plugin_id, "status": "deployed"}
