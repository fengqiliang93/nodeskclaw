from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.backup import BackupStatus
from app.models.instance import InstanceStatus
from app.services import backup_service


def _result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def test_decode_base64_chunk_accepts_wrapped_or_unpadded_data() -> None:
    assert backup_service._decode_base64_chunk("YQ==\n") == b"a"
    assert backup_service._decode_base64_chunk("YQ") == b"a"


@pytest.mark.asyncio
async def test_execute_clone_pipeline_marks_instance_failed_when_backup_fails(monkeypatch) -> None:
    ctx = SimpleNamespace(instance_id="clone-1")
    new_inst = SimpleNamespace(
        id="clone-1",
        status=InstanceStatus.running,
        compute_provider="k8s",
        runtime="openclaw",
        namespace="ns-1",
        slug="slug-1",
        cluster_id="cluster-1",
    )
    source_inst = SimpleNamespace(id="source-1")

    first_session = AsyncMock()
    first_session.__aenter__ = AsyncMock(return_value=first_session)
    first_session.__aexit__ = AsyncMock(return_value=False)
    first_session.execute = AsyncMock(side_effect=[_result(new_inst), _result(source_inst)])

    second_session = AsyncMock()
    second_session.__aenter__ = AsyncMock(return_value=second_session)
    second_session.__aexit__ = AsyncMock(return_value=False)
    second_session.execute = AsyncMock(return_value=_result(new_inst))

    async_session_factory = MagicMock(side_effect=[first_session, second_session])
    monkeypatch.setattr("app.core.deps.async_session_factory", async_session_factory)
    monkeypatch.setattr(
        "app.services.deploy_service.execute_deploy_pipeline",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        backup_service,
        "_wait_for_backup",
        AsyncMock(return_value=SimpleNamespace(status=BackupStatus.failed, message="Incorrect padding")),
    )

    with pytest.raises(RuntimeError, match="Incorrect padding"):
        await backup_service._execute_clone_pipeline(ctx, "backup-1", "deploy-1", "source-1")

    assert new_inst.status == InstanceStatus.failed
    first_session.commit.assert_awaited_once()
    second_session.commit.assert_awaited_once()
