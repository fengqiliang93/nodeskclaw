from types import SimpleNamespace

from app.core.config import settings
from app.services import llm_config_service
from app.services.llm_config_service import _build_providers_config
from app.utils.jsonc import (
    DEFAULT_SEARXNG_BASE_URL,
    ensure_browser_no_sandbox,
    ensure_searxng_web_search,
    ensure_tools_allow_full_default,
)


def test_nodeskclaw_tool_names_are_complete() -> None:
    assert llm_config_service.NODESKCLAW_TOOL_NAMES == (
        "nodeskclaw_blackboard",
        "nodeskclaw_topology",
        "nodeskclaw_performance",
        "nodeskclaw_proposals",
        "nodeskclaw_gene_discovery",
        "nodeskclaw_file_download",
        "nodeskclaw_chat_history",
        "nodeskclaw_shared_files",
    )


def test_build_providers_config_normalizes_openai_api_type(monkeypatch) -> None:
    monkeypatch.setattr(settings, "LLM_PROXY_INTERNAL_URL", "http://llm-proxy:18080")
    monkeypatch.setattr(settings, "LLM_PROXY_URL", "http://llm-proxy:18080")

    providers = _build_providers_config(
        [SimpleNamespace(provider="custom", key_source="org", selected_models=None, api_type="openai")],
        "instance-wp-token",
        {},
    )

    assert providers["custom"]["api"] == "openai-completions"


def test_nodeskclaw_channel_keeps_optional_tools_enabled() -> None:
    config = {
        "channels": {"nodeskclaw": {"accounts": {"default": {}}}},
        "tools": {
            "allow": [
                "browser_open",
            ]
        }
    }

    llm_config_service.ensure_nodeskclaw_tool_allow(config)

    assert config["tools"]["allow"] == [
        "browser_open",
        *llm_config_service.NODESKCLAW_TOOL_NAMES,
    ]


def test_tools_allow_defaults_to_full_for_legacy_empty_state() -> None:
    config = {"tools": {}}
    ensure_tools_allow_full_default(config)
    assert config["tools"]["allow"] == ["*"]


def test_tools_allow_upgrades_exec_only_legacy_state() -> None:
    config = {"tools": {"allow": ["exec"]}}
    ensure_tools_allow_full_default(config)
    assert config["tools"]["allow"] == ["*"]


def test_tools_allow_collapses_star_plus_legacy_items() -> None:
    config = {"tools": {"allow": ["*", "nodeskclaw_blackboard"]}}
    ensure_tools_allow_full_default(config)
    assert config["tools"]["allow"] == ["*"]


def test_browser_no_sandbox_is_forced_enabled() -> None:
    config = {"browser": {"noSandbox": False}}
    ensure_browser_no_sandbox(config)
    assert config["browser"]["noSandbox"] is True


def test_searxng_web_search_is_forced_enabled() -> None:
    config = {}
    ensure_searxng_web_search(config, DEFAULT_SEARXNG_BASE_URL)

    assert config["plugins"]["entries"]["searxng"]["config"]["webSearch"]["baseUrl"] == DEFAULT_SEARXNG_BASE_URL
    assert config["tools"]["web"]["search"]["enabled"] is True
    assert config["tools"]["web"]["search"]["provider"] == "searxng"
