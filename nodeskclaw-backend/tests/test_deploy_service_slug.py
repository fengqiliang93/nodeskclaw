from app.services.deploy_service import build_auto_slug


def test_build_auto_slug_keeps_ascii_slug() -> None:
    assert build_auto_slug("OpenClaw Clone 01") == "openclaw-clone-01"


def test_build_auto_slug_uses_deterministic_fallback_for_non_ascii() -> None:
    slug = build_auto_slug("验收克隆-冯起良")
    assert slug.startswith("instance-")
    assert len(slug) == len("instance-") + 8


def test_build_auto_slug_supports_custom_fallback_prefix() -> None:
    slug = build_auto_slug(
        "验收克隆-冯起良",
        fallback_prefix="openclaw-executive-fengqiliang-clone",
    )
    assert slug.startswith("openclaw-executive-fengqiliang-clone-")
