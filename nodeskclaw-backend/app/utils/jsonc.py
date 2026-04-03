"""JSONC (JSON with Comments) parsing utilities.

Provides safe parsing for openclaw.json and similar config files
that may contain JS-style comments (// and /* */) or trailing commas.
Also includes config-level guards applied before every write.
"""

import json
import re


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
