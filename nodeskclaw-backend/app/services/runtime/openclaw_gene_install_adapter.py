"""OpenClaw-specific gene installation adapter.

Handles:
- Skill file deployment to .openclaw/skills/{name}/SKILL.md with YAML frontmatter
- tool_allow whitelist management in openclaw.json
- Python script deployment to ~/.deskclaw/tools/
- Config merging into openclaw.json
- Skill snapshot invalidation + evolution notification injection
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from app.services.runtime.gene_install_adapter import GeneInstallAdapter

if TYPE_CHECKING:
    from app.services.nfs_mount import RemoteFS

logger = logging.getLogger(__name__)

OPENCLAW_CONFIG_REL = ".openclaw/openclaw.json"
SKILLS_DIR_REL = ".openclaw/skills"
SKILLS_EXTRA_DIR = "/root/.openclaw/skills"
SCRIPTS_DIR_REL = ".deskclaw/tools"
_SESSIONS_REL = ".openclaw/agents/main/sessions/sessions.json"


class OpenClawGeneInstallAdapter(GeneInstallAdapter):

    async def deploy_skill(
        self, fs: RemoteFS, skill_name: str, content: str, description: str = "",
    ) -> None:
        if not content.lstrip().startswith("---"):
            desc = description or f"Skill: {skill_name}"
            front_matter = f"---\nname: {skill_name}\ndescription: {desc}\n---\n\n"
            content = front_matter + content

        await fs.mkdir(f"{SKILLS_DIR_REL}/{skill_name}")
        await fs.write_text(f"{SKILLS_DIR_REL}/{skill_name}/SKILL.md", content)
        await self._ensure_skills_discovery(fs)

    async def allow_tools(self, fs: RemoteFS, tool_names: list[str]) -> None:
        if not tool_names:
            return
        config = await self._read_config(fs)
        tools = config.setdefault("tools", {})
        allow = tools.get("allow", [])
        if not isinstance(allow, list):
            allow = []
        existing_set = set(allow)
        for name in tool_names:
            if name not in existing_set:
                allow.append(name)
                existing_set.add(name)
        tools["allow"] = allow
        await self._write_config(fs, config)

    async def deploy_scripts(self, fs: RemoteFS, scripts: dict[str, str]) -> None:
        if not scripts:
            return
        await fs.mkdir(SCRIPTS_DIR_REL)
        for filename, content in scripts.items():
            await fs.write_text(f"{SCRIPTS_DIR_REL}/{filename}", content)

    async def apply_config(self, fs: RemoteFS, config_patch: dict) -> None:
        if not config_patch:
            return
        config = await self._read_config(fs)
        for key, val in config_patch.items():
            if isinstance(val, dict) and isinstance(config.get(key), dict):
                config[key].update(val)
            else:
                config[key] = val
        await self._write_config(fs, config)

    async def invalidate_cache(self, fs: RemoteFS, skill_name: str, event: str = "installed") -> None:
        from app.services.openclaw_session import (
            inject_evolution_notification,
            invalidate_skill_snapshots,
        )
        await invalidate_skill_snapshots(fs)
        await inject_evolution_notification(fs, skill_name, event)

    async def remove_skill(self, fs: RemoteFS, skill_name: str) -> None:
        await fs.remove(f"{SKILLS_DIR_REL}/{skill_name}")

    async def post_remove_cleanup(self, fs: RemoteFS, skill_name: str) -> None:
        from app.services.openclaw_session import (
            ensure_skills_discovery,
            inject_evolution_notification,
            invalidate_skill_snapshots,
        )
        await ensure_skills_discovery(fs)
        await invalidate_skill_snapshots(fs)
        await inject_evolution_notification(fs, skill_name, "uninstalled")

    async def _ensure_skills_discovery(self, fs: RemoteFS) -> None:
        config = await self._read_config(fs)
        skills = config.setdefault("skills", {})
        load = skills.setdefault("load", {})
        extra_dirs = load.setdefault("extraDirs", [])
        if SKILLS_EXTRA_DIR not in extra_dirs:
            extra_dirs.append(SKILLS_EXTRA_DIR)
            await self._write_config(fs, config)

    async def _read_config(self, fs: RemoteFS) -> dict:
        raw = await fs.read_text(OPENCLAW_CONFIG_REL)
        if raw is None:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    async def _write_config(self, fs: RemoteFS, config: dict) -> None:
        await fs.write_text(
            OPENCLAW_CONFIG_REL,
            json.dumps(config, indent=2, ensure_ascii=False),
        )
