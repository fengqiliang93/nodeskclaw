"""ProcessComputeProvider — manages agent instances as local OS processes."""

from __future__ import annotations

import asyncio
import logging
import os
import signal

from app.services.runtime.compute.base import (
    ComputeHandle,
    InstanceComputeConfig,
)

logger = logging.getLogger(__name__)


class ProcessComputeProvider:
    """Runs agent runtimes as local subprocess, suitable for development/testing."""

    provider_id = "process"

    def __init__(self) -> None:
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    async def create_instance(
        self, config: InstanceComputeConfig, **kwargs,
    ) -> ComputeHandle:
        logger.info("ProcessComputeProvider.create_instance: %s", config.instance_id)

        cmd = config.extra.get("command", "")
        if not cmd:
            return ComputeHandle(
                provider=self.provider_id,
                instance_id=config.instance_id,
                namespace="local",
                status="failed",
                extra={"error": "no command specified"},
            )

        env = {**os.environ, **{k: str(v) for k, v in config.env_vars.items()}}
        port = config.extra.get("port", 3000)

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            self._processes[config.instance_id] = proc

            return ComputeHandle(
                provider=self.provider_id,
                instance_id=config.instance_id,
                namespace="local",
                endpoint=f"http://localhost:{port}",
                status="running",
                extra={"pid": proc.pid},
            )
        except Exception as e:
            logger.error("Process create_instance failed: %s", e)
            return ComputeHandle(
                provider=self.provider_id,
                instance_id=config.instance_id,
                namespace="local",
                status="failed",
                extra={"error": str(e)},
            )

    async def destroy_instance(self, handle: ComputeHandle, **kwargs) -> None:
        logger.info("ProcessComputeProvider.destroy_instance: %s", handle.instance_id)
        proc = self._processes.pop(handle.instance_id, None)
        if proc and proc.returncode is None:
            try:
                proc.send_signal(signal.SIGTERM)
                try:
                    await asyncio.wait_for(proc.wait(), timeout=10)
                except asyncio.TimeoutError:
                    proc.kill()
            except ProcessLookupError:
                pass

    async def get_status(self, handle: ComputeHandle) -> str:
        proc = self._processes.get(handle.instance_id)
        if proc is None:
            return "stopped"
        if proc.returncode is not None:
            return "exited"
        return "running"

    async def get_endpoint(self, handle: ComputeHandle) -> str:
        return handle.endpoint

    async def get_logs(self, handle: ComputeHandle, *, tail: int = 50) -> str:
        proc = self._processes.get(handle.instance_id)
        if proc and proc.stdout:
            try:
                data = await asyncio.wait_for(proc.stdout.read(8192), timeout=1)
                return data.decode() if data else ""
            except (asyncio.TimeoutError, Exception):
                pass
        return ""

    async def restart_instance(self, handle: ComputeHandle, config: InstanceComputeConfig) -> ComputeHandle:
        await self.destroy_instance(handle)
        return await self.create_instance(config)

    async def scale_instance(self, handle: ComputeHandle, replicas: int) -> ComputeHandle:
        raise NotImplementedError("ProcessComputeProvider 不支持水平扩缩容")

    async def update_instance(
        self, handle: ComputeHandle, config: InstanceComputeConfig,
    ) -> ComputeHandle:
        await self.destroy_instance(handle)
        return await self.create_instance(config)

    async def health_check(self, handle: ComputeHandle) -> dict:
        proc = self._processes.get(handle.instance_id)
        if proc is None or proc.returncode is not None:
            return {"healthy": False, "detail": "process not running"}
        from app.services.runtime.compute.base import http_probe
        return await http_probe(handle.endpoint)
