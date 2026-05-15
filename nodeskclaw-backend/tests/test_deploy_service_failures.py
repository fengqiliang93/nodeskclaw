from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import deploy_service


@pytest.mark.asyncio
async def test_execute_deploy_inner_does_not_crash_when_adapter_not_initialized(monkeypatch) -> None:
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.execute = AsyncMock(side_effect=RuntimeError("db unavailable"))
    session.commit = AsyncMock()

    async_session_factory = MagicMock(return_value=session)
    published_events: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(
        deploy_service.event_bus,
        "publish",
        lambda *args, **kwargs: published_events.append((args, kwargs)),
    )

    ctx = SimpleNamespace(
        record_id="deploy-1",
        cluster_id="cluster-1",
        name="验收实例",
        namespace="nodeskclaw-default-acceptance",
        org_id="org-1",
        instance_id="instance-1",
        image_version="v1",
    )

    await deploy_service._execute_deploy_inner(
        ctx=ctx,
        async_session_factory=async_session_factory,
        get_config=MagicMock(),
        total=2,
        steps=["预检", "创建命名空间"],
    )

    assert published_events[-1][0][0] == "deploy_progress"
    assert published_events[-1][0][1]["status"] == "failed"
