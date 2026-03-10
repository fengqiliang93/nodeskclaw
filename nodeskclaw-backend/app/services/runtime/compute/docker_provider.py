"""DockerComputeProvider — manages agent instances as Docker Compose services."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile

from app.services.runtime.compute.base import (
    ComputeHandle,
    CompanionSpec,
    InstanceComputeConfig,
)

logger = logging.getLogger(__name__)


def _build_compose_yaml(config: InstanceComputeConfig) -> dict:
    """Generate a docker-compose service definition."""
    services: dict = {}

    main_service = {
        "image": config.env_vars.get("DOCKER_IMAGE", f"deskclaw:{config.image_version}"),
        "container_name": config.slug,
        "environment": {k: str(v) for k, v in config.env_vars.items()},
        "ports": ["3000"],
        "restart": "unless-stopped",
        "platform": "linux/amd64",
    }
    if config.mem_limit:
        main_service["mem_limit"] = config.mem_limit
    services["agent"] = main_service

    if config.companion and config.companion.enabled:
        companion = {
            "image": config.companion.image or "deskclaw-companion:latest",
            "container_name": f"{config.slug}-companion",
            "environment": config.companion.env_vars,
            "ports": [str(config.companion.port)],
            "restart": "unless-stopped",
            "platform": "linux/amd64",
            "depends_on": ["agent"],
        }
        services["companion"] = companion

    return {"version": "3.8", "services": services}


class DockerComputeProvider:
    """Docker compose-based compute provider for local/dev agent instances."""

    provider_id = "docker"

    async def create_instance(
        self, config: InstanceComputeConfig, **kwargs,
    ) -> ComputeHandle:
        logger.info(
            "DockerComputeProvider.create_instance: %s",
            config.instance_id,
        )

        compose = _build_compose_yaml(config)
        project_dir = os.path.join(tempfile.gettempdir(), "deskclaw-docker", config.slug)
        os.makedirs(project_dir, exist_ok=True)

        compose_path = os.path.join(project_dir, "docker-compose.yml")
        import yaml
        try:
            with open(compose_path, "w") as f:
                yaml.dump(compose, f)
        except ImportError:
            with open(compose_path, "w") as f:
                json.dump(compose, f, indent=2)

        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "compose", "-f", compose_path, "up", "-d",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error("docker compose up failed: %s", stderr.decode())
                return ComputeHandle(
                    provider=self.provider_id,
                    instance_id=config.instance_id,
                    namespace="docker-local",
                    status="failed",
                    extra={"error": stderr.decode()[:500]},
                )
        except FileNotFoundError:
            logger.warning("docker compose not found, skipping actual container creation")

        return ComputeHandle(
            provider=self.provider_id,
            instance_id=config.instance_id,
            namespace="docker-local",
            endpoint=f"http://{config.slug}:3000",
            status="running",
            extra={"compose_path": compose_path},
        )

    async def destroy_instance(self, handle: ComputeHandle, **kwargs) -> None:
        logger.info(
            "DockerComputeProvider.destroy_instance: %s",
            handle.instance_id,
        )
        compose_path = handle.extra.get("compose_path", "")
        if compose_path and os.path.exists(compose_path):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "docker", "compose", "-f", compose_path, "down",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
            except Exception as e:
                logger.warning("docker compose down failed: %s", e)

    async def get_status(self, handle: ComputeHandle) -> str:
        return handle.status

    async def get_endpoint(self, handle: ComputeHandle) -> str:
        return handle.endpoint

    async def get_logs(self, handle: ComputeHandle, *, tail: int = 50) -> str:
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "logs", "--tail", str(tail), handle.instance_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await proc.communicate()
            return stdout.decode() if stdout else ""
        except Exception:
            return ""

    async def update_instance(
        self, handle: ComputeHandle, config: InstanceComputeConfig,
    ) -> ComputeHandle:
        logger.info(
            "DockerComputeProvider.update_instance: %s",
            handle.instance_id,
        )
        await self.destroy_instance(handle)
        return await self.create_instance(config)
