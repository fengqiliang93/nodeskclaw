"""JSONC (JSON with Comments) parsing utilities.

Provides safe parsing for openclaw.json and similar config files
that may contain JS-style comments (// and /* */) or trailing commas.
Also includes config-level guards applied before every write.
"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)


def strip_jsonc(text: str) -> str:
    """Strip JS-style comments (// and /* */) and trailing commas from JSON text."""
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return text


def parse_config_json(raw: str) -> dict:
    """Parse a JSON string that may contain JSONC comments.

    Tries standard json.loads first; falls back to stripping comments.
    Raises ValueError if the text cannot be parsed even after stripping.
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    try:
        return json.loads(strip_jsonc(raw))
    except json.JSONDecodeError as e:
        raise ValueError(
            f"JSON 格式无法解析（已尝试去除注释）: {e}"
        ) from e


def deep_merge_config(base: dict, patch: dict) -> dict:
    """Recursively merge *patch* into *base* (mutates *base* in place).

    - dict + dict  -> recurse (preserves keys in *base* not mentioned in *patch*)
    - anything else -> *patch* value replaces *base* value
    """
    for key, val in patch.items():
        if isinstance(val, dict) and isinstance(base.get(key), dict):
            deep_merge_config(base[key], val)
        else:
            base[key] = val
    return base


# Paths must stay in sync with CHANNEL_PLUGIN_DIR / LEARNING_PLUGIN_DIR
# constructed in llm_config_service.py.
_CHANNEL_PLUGIN_PATHS: dict[str, str] = {
    "nodeskclaw": "/root/.openclaw/extensions/openclaw-channel-nodeskclaw",
    "learning": "/root/.openclaw/extensions/openclaw-channel-learning",
}

NODESKCLAW_TOOL_NAMES = (
    "nodeskclaw_blackboard",
    "nodeskclaw_topology",
    "nodeskclaw_performance",
    "nodeskclaw_proposals",
    "nodeskclaw_gene_discovery",
    "nodeskclaw_file_download",
    "nodeskclaw_chat_history",
    "nodeskclaw_shared_files",
)

DEFAULT_SEARXNG_BASE_URL = "http://searxng-web.nodeskclaw-staging.svc.cluster.local:8080"
DEFAULT_OPENCLAW_PRIMARY_MODEL = "custom/ark-code-latest"
DEFAULT_OPENCLAW_PRIMARY_MODEL_ID = "ark-code-latest"


def ensure_tools_allow_full_default(config: dict) -> dict:
    """Default OpenClaw tool permission to full when config is legacy/minimal.

    We only upgrade known legacy states to avoid overriding deliberate custom
    restrictions:
    - tools.allow missing / empty
    - tools.allow == ["exec"] (legacy minimal profile)
    - tools.allow contains only NoDeskClaw optional tools (pre-full migration)
    """
    tools = config.setdefault("tools", {})
    allow = tools.get("allow")
    if not isinstance(allow, list):
        tools["allow"] = ["*"]
        return config

    normalized = [str(item).strip() for item in allow if str(item).strip()]
    if "*" in normalized:
        tools["allow"] = ["*"]
        return config

    allow_set = set(normalized)
    if (
        not allow_set
        or allow_set == {"exec"}
        or allow_set.issubset(set(NODESKCLAW_TOOL_NAMES))
    ):
        tools["allow"] = ["*"]
        return config

    tools["allow"] = normalized
    return config


def ensure_channel_plugin_integrity(config: dict) -> dict:
    """If a channel plugin section exists in *channels*, guarantee the
    matching plugin load-path and entries record are present too.

    Called before every openclaw.json write via the gene-install adapter
    so that a Gene's ``runtime_config`` patch can never silently remove
    the channel-plugin wiring.
    """
    channels = config.get("channels", {})
    for channel_id, plugin_path in _CHANNEL_PLUGIN_PATHS.items():
        if channel_id not in channels:
            continue
        plugins = config.setdefault("plugins", {})
        load = plugins.setdefault("load", {})
        paths = load.setdefault("paths", [])
        if plugin_path not in paths:
            logger.warning(
                "ensure_channel_plugin_integrity: %s plugin path missing, auto-repaired",
                channel_id,
            )
            paths.append(plugin_path)
        entries = plugins.setdefault("entries", {})
        if channel_id not in entries:
            logger.warning(
                "ensure_channel_plugin_integrity: %s plugin entry missing, auto-repaired",
                channel_id,
            )
            entries[channel_id] = {"enabled": True}
    return config


def ensure_nodeskclaw_tool_allow(config: dict) -> dict:
    """When the NoDeskClaw channel is enabled, keep its optional tools enabled too."""
    channels = config.get("channels")
    if not isinstance(channels, dict) or "nodeskclaw" not in channels:
        return config

    tools = config.setdefault("tools", {})
    allow = tools.get("allow")
    if not isinstance(allow, list):
        allow = []

    existing = {str(item) for item in allow}
    for tool_name in NODESKCLAW_TOOL_NAMES:
        if tool_name not in existing:
            allow.append(tool_name)
            existing.add(tool_name)

    tools["allow"] = allow
    return config


def ensure_exec_security(config: dict) -> dict:
    """Enforce headless exec policy: security=full + ask=off.

    NoDeskClaw runs in non-interactive K8s pods where exec approval
    prompts would hang forever. This is called before every openclaw.json
    write to guarantee the setting is never lost.
    """
    tools = config.setdefault("tools", {})
    exec_cfg = tools.setdefault("exec", {})
    exec_cfg["security"] = "full"
    exec_cfg["ask"] = "off"
    return config


def ensure_browser_no_sandbox(config: dict) -> dict:
    """Enforce browser.noSandbox=true for root/container runtimes."""
    browser = config.setdefault("browser", {})
    browser["noSandbox"] = True
    return config


def ensure_searxng_web_search(config: dict, base_url: str | None = None) -> dict:
    """Enforce OpenClaw web_search to use the self-hosted SearXNG provider."""
    resolved_base_url = (base_url or DEFAULT_SEARXNG_BASE_URL).strip()
    if not resolved_base_url:
        return config

    plugins = config.setdefault("plugins", {})
    entries = plugins.setdefault("entries", {})
    searxng = entries.setdefault("searxng", {})
    searxng_cfg = searxng.setdefault("config", {})
    web_search_cfg = searxng_cfg.setdefault("webSearch", {})
    web_search_cfg["baseUrl"] = resolved_base_url

    tools = config.setdefault("tools", {})
    web_cfg = tools.setdefault("web", {})
    search_cfg = web_cfg.setdefault("search", {})
    search_cfg["enabled"] = True
    search_cfg["provider"] = "searxng"
    search_cfg.setdefault("maxResults", 5)
    search_cfg.setdefault("timeoutSeconds", 30)
    return config


def ensure_agent_defaults(config: dict) -> dict:
    """Enforce shared agent defaults for all OpenClaw AI employee instances."""
    agents = config.setdefault("agents", {})
    defaults = agents.setdefault("defaults", {})

    heartbeat = defaults.setdefault("heartbeat", {})
    heartbeat["every"] = "3h"
    heartbeat["lightContext"] = True
    heartbeat["isolatedSession"] = True

    model_cfg = defaults.setdefault("model", {})
    model_cfg["primary"] = DEFAULT_OPENCLAW_PRIMARY_MODEL

    providers = config.get("models", {}).get("providers", {})
    custom_provider = providers.get("custom")
    if isinstance(custom_provider, dict):
        models = custom_provider.get("models")
        if isinstance(models, list):
            existing_ids = {
                str(item.get("id")).strip()
                for item in models
                if isinstance(item, dict) and str(item.get("id")).strip()
            }
            if DEFAULT_OPENCLAW_PRIMARY_MODEL_ID not in existing_ids:
                models.insert(
                    0,
                    {
                        "id": DEFAULT_OPENCLAW_PRIMARY_MODEL_ID,
                        "name": DEFAULT_OPENCLAW_PRIMARY_MODEL_ID,
                    },
                )

    return config
