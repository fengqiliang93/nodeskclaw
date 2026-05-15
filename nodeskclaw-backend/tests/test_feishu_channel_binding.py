import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.corridors import _normalize_human_hex_channel_binding
from app.services.channel_config_service import (
    _apply_feishu_node_selector,
    _apply_openclaw_feishu_platform_defaults,
    _extract_pv_node_name,
    _parse_node_selector,
    _selector_matches_labels,
    _sync_openclaw_feishu_default_account,
    has_openclaw_feishu_channel,
)
from app.services.channel_adapters.feishu_ws_client import (
    resolve_feishu_ws_client_config,
    should_route_feishu_message,
)
from app.services.feishu_config import normalize_openclaw_feishu_config


def test_normalize_human_hex_channel_binding_promotes_chat_id_and_feishu_type() -> None:
    channel_type, channel_config = _normalize_human_hex_channel_binding(
        None,
        {"chatId": "oc_test_chat", "allowFrom": ["*"]},
    )

    assert channel_type == "feishu"
    assert channel_config == {"chat_id": "oc_test_chat", "allowFrom": ["*"]}


def test_sync_openclaw_feishu_default_account_creates_default_account_block() -> None:
    merged = _sync_openclaw_feishu_default_account(
        {},
        {
            "appId": "cli_test",
            "appSecret": "secret",
            "connectionMode": "websocket",
            "allowFrom": ["*"],
        },
    )

    assert merged["defaultAccount"] == "default"
    assert merged["accounts"]["default"]["appId"] == "cli_test"
    assert merged["accounts"]["default"]["appSecret"] == "secret"
    assert merged["accounts"]["default"]["connectionMode"] == "websocket"
    assert merged["accounts"]["default"]["allowFrom"] == ["*"]


def test_apply_openclaw_feishu_platform_defaults_backfills_allowlists() -> None:
    out = _apply_openclaw_feishu_platform_defaults(
        {
            "appId": "cli_test",
            "appSecret": "secret",
        }
    )

    assert out["connectionMode"] == "websocket"
    assert out["streaming"] is True
    assert out["blockStreaming"] is False
    assert "dmPolicy" not in out
    assert "groupPolicy" not in out
    assert "allowFrom" not in out
    assert "groupAllowFrom" not in out


def test_sync_openclaw_feishu_default_account_backfills_account_allowlists() -> None:
    merged = _sync_openclaw_feishu_default_account(
        {"accounts": {"default": {"appId": "cli_test"}}, "defaultAccount": "default"},
        {
            "appId": "cli_test",
            "appSecret": "secret",
            "connectionMode": "websocket",
            "dmPolicy": "open",
            "groupPolicy": "open",
            "allowFrom": ["*"],
            "groupAllowFrom": ["*"],
        },
    )

    default_account = merged["accounts"]["default"]
    assert default_account["allowFrom"] == ["*"]
    assert default_account["groupAllowFrom"] == ["*"]


def test_sync_openclaw_feishu_default_account_mirrors_topic_session_mode() -> None:
    merged = _sync_openclaw_feishu_default_account(
        {"accounts": {"default": {}}, "defaultAccount": "default"},
        {"topicSessionMode": "enabled"},
    )

    assert merged["accounts"]["default"]["topicSessionMode"] == "enabled"


def test_sync_openclaw_feishu_default_account_mirrors_streaming_flags() -> None:
    merged = _sync_openclaw_feishu_default_account(
        {"accounts": {"default": {}}, "defaultAccount": "default"},
        {"streaming": True, "blockStreaming": False},
    )

    assert merged["accounts"]["default"]["streaming"] is True
    assert merged["accounts"]["default"]["blockStreaming"] is False


def test_parse_node_selector_supports_kv_pairs() -> None:
    out = _parse_node_selector("node-role.kubernetes.io/control-plane=true,kubernetes.io/arch=amd64")
    assert out == {
        "node-role.kubernetes.io/control-plane": "true",
        "kubernetes.io/arch": "amd64",
    }


def test_parse_node_selector_supports_json() -> None:
    out = _parse_node_selector('{"node-role.kubernetes.io/control-plane":"true"}')
    assert out == {"node-role.kubernetes.io/control-plane": "true"}


def test_normalize_openclaw_feishu_config_coerces_allowlists() -> None:
    out = normalize_openclaw_feishu_config(
        {
            "channels": {
                "feishu": {
                    "dmPolicy": "open",
                    "groupPolicy": "open",
                    "allowFrom": "*",
                    "groupAllowFrom": '["*"]',
                    "chatId": "legacy-chat",
                    "accounts": {
                        "default": {
                            "dmPolicy": "open",
                            "groupPolicy": "open",
                            "allowFrom": "u_1,u_2",
                            "groupAllowFrom": "u_3",
                            "chat_id": "legacy-chat",
                        }
                    },
                }
            }
        }
    )

    feishu = out["channels"]["feishu"]
    assert feishu["allowFrom"] == ["*"]
    assert feishu["groupAllowFrom"] == ["*"]
    assert "chatId" not in feishu
    default_account = feishu["accounts"]["default"]
    assert default_account["allowFrom"] == ["u_1", "u_2"]
    assert default_account["groupAllowFrom"] == ["u_3"]
    assert "chat_id" not in default_account


def test_normalize_openclaw_feishu_config_migrates_legacy_mention_mode() -> None:
    out = normalize_openclaw_feishu_config(
        {
            "channels": {
                "feishu": {
                    "groupPolicy": "mention",
                }
            }
        }
    )

    feishu = out["channels"]["feishu"]
    assert feishu["groupPolicy"] == "open"
    assert feishu["requireMention"] is True
    assert feishu["streaming"] is True
    assert feishu["blockStreaming"] is False


def test_normalize_openclaw_feishu_config_forces_streaming_enabled() -> None:
    out = normalize_openclaw_feishu_config(
        {
            "channels": {
                "feishu": {
                    "streaming": False,
                    "blockStreaming": True,
                    "accounts": {
                        "default": {
                            "streaming": False,
                            "blockStreaming": True,
                        }
                    },
                }
            }
        }
    )

    feishu = out["channels"]["feishu"]
    assert feishu["streaming"] is True
    assert feishu["blockStreaming"] is False
    assert feishu["accounts"]["default"]["streaming"] is True
    assert feishu["accounts"]["default"]["blockStreaming"] is False


def test_normalize_openclaw_feishu_config_forces_require_mention_when_legacy_mode_conflicts() -> None:
    out = normalize_openclaw_feishu_config(
        {
            "channels": {
                "feishu": {
                    "groupPolicy": "mention",
                    "requireMention": False,
                    "groups": {
                        "oc_test": {
                            "groupPolicy": "mention",
                            "requireMention": False,
                        }
                    },
                }
            }
        }
    )

    feishu = out["channels"]["feishu"]
    assert feishu["groupPolicy"] == "open"
    assert feishu["requireMention"] is True
    assert feishu["groups"]["oc_test"]["groupPolicy"] == "open"
    assert feishu["groups"]["oc_test"]["requireMention"] is True


def test_apply_openclaw_feishu_platform_defaults_force_streaming_flags() -> None:
    out = _apply_openclaw_feishu_platform_defaults(
        {
            "streaming": False,
            "blockStreaming": True,
        }
    )
    assert out["streaming"] is True
    assert out["blockStreaming"] is False


def test_resolve_feishu_ws_client_config_supports_camel_case() -> None:
    resolved = resolve_feishu_ws_client_config(
        {
            "connectionMode": "websocket",
            "appId": "cli_test",
            "appSecret": "secret",
            "encryptKey": "enc",
            "verificationToken": "verify",
        }
    )

    assert resolved == {
        "app_id": "cli_test",
        "app_secret": "secret",
        "encrypt_key": "enc",
        "verification_token": "verify",
    }


def test_should_route_feishu_message_requires_direct_mention_in_group() -> None:
    allowed = should_route_feishu_message(
        {
            "groupPolicy": "open",
            "requireMention": True,
        },
        chat_type="group",
        chat_id="oc_group",
        sender_open_id="ou_user",
        mention_tokens=set(),
    )

    assert allowed is False


def test_should_route_feishu_message_accepts_explicit_group_override() -> None:
    allowed = should_route_feishu_message(
        {
            "groupPolicy": "allowlist",
            "groups": {
                "oc_group": {
                    "requireMention": False,
                }
            },
        },
        chat_type="group",
        chat_id="oc_group",
        sender_open_id="ou_user",
        mention_tokens=set(),
    )

    assert allowed is True


def test_should_route_feishu_message_rejects_non_group_allowlist_chat() -> None:
    allowed = should_route_feishu_message(
        {
            "groupPolicy": "allowlist",
            "groupAllowFrom": ["oc_other"],
            "requireMention": False,
        },
        chat_type="group",
        chat_id="oc_group",
        sender_open_id="ou_user",
        mention_tokens={"ou_bot"},
    )

    assert allowed is False


def test_has_openclaw_feishu_channel_detects_enabled_channel() -> None:
    assert has_openclaw_feishu_channel({"channels": {"feishu": {"accounts": {"default": {}}}}}) is True
    assert has_openclaw_feishu_channel({"channels": {"feishu": {}}}) is False
    assert has_openclaw_feishu_channel({"channels": {"dingtalk": {"token": "x"}}}) is False


def test_selector_matches_labels_requires_all_pairs() -> None:
    labels = {
        "node-role.kubernetes.io/control-plane": "true",
        "kubernetes.io/hostname": "ubuntu24new0001",
    }
    assert _selector_matches_labels(
        {"node-role.kubernetes.io/control-plane": "true"},
        labels,
    ) is True
    assert _selector_matches_labels(
        {"node-role.kubernetes.io/control-plane": "true", "kubernetes.io/hostname": "ubuntu24ai0001"},
        labels,
    ) is False


def test_extract_pv_node_name_reads_hostname_affinity() -> None:
    class _Expr:
        key = "kubernetes.io/hostname"
        values = ["ubuntu24ai0001"]

    class _Term:
        match_expressions = [_Expr()]

    class _Required:
        node_selector_terms = [_Term()]

    class _Affinity:
        required = _Required()

    class _Spec:
        node_affinity = _Affinity()

    class _Pv:
        spec = _Spec()

    assert _extract_pv_node_name(_Pv()) == "ubuntu24ai0001"


@pytest.mark.asyncio
async def test_apply_feishu_node_selector_clears_conflicting_local_pvc_selector(monkeypatch) -> None:
    instance = SimpleNamespace(
        name="sample-feishu-bot-test",
        slug="sample-feishu-bot-test",
        namespace="nodeskclaw-default-sample-feishu-bot-test",
        cluster_id="cluster-1",
        compute_provider="k8s",
        advanced_config=json.dumps({
            "node_selector": {
                "node-role.kubernetes.io/control-plane": "true",
                "kubernetes.io/arch": "amd64",
            }
        }, ensure_ascii=False),
    )
    db = AsyncMock()
    cluster = SimpleNamespace(id="cluster-1")
    result = MagicMock()
    result.scalar_one_or_none.return_value = cluster
    db.execute.return_value = result

    k8s = SimpleNamespace(
        apps=SimpleNamespace(patch_namespaced_deployment=AsyncMock()),
    )

    monkeypatch.setattr(
        "app.services.channel_config_service.settings.FEISHU_NODE_SELECTOR",
        "node-role.kubernetes.io/control-plane=true",
    )
    monkeypatch.setattr(
        "app.services.channel_config_service.require_k8s_client",
        AsyncMock(return_value=k8s),
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.runtime.registries.compute_registry.require_k8s_client",
        AsyncMock(return_value=k8s),
    )
    monkeypatch.setattr(
        "app.services.channel_config_service._has_incompatible_local_pvc",
        AsyncMock(return_value=True),
    )

    await _apply_feishu_node_selector(instance, db)

    assert json.loads(instance.advanced_config) == {
        "node_selector": {
            "kubernetes.io/arch": "amd64",
        }
    }
    k8s.apps.patch_namespaced_deployment.assert_awaited_once_with(
        "sample-feishu-bot-test",
        "nodeskclaw-default-sample-feishu-bot-test",
        {"spec": {"template": {"spec": {"nodeSelector": {"kubernetes.io/arch": "amd64"}}}}},
    )
