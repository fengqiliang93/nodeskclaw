"""Business logic for the engine version catalog."""

import logging
import re

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.base import not_deleted
from app.models.engine_version import EngineVersion

logger = logging.getLogger(__name__)


def _version_key(v: str) -> tuple[int, ...]:
    nums = [int(x) for x in re.findall(r"\d+", (v or "").lstrip("v"))]
    return tuple(nums) if nums else (0,)


async def _ensure_catalog_initialized(runtime: str, db: AsyncSession) -> None:
    existing = await db.execute(
        select(EngineVersion)
        .where(EngineVersion.runtime == runtime, not_deleted(EngineVersion))
        .order_by(EngineVersion.created_at.desc())
        .limit(1)
    )
    has_any = existing.scalar_one_or_none() is not None

    if not has_any:
        from app.models.instance import Instance

        rows = (await db.execute(
            select(Instance.image_version)
            .where(
                Instance.image_version.isnot(None),
                Instance.image_version != "",
                Instance.deleted_at.is_(None),
                or_(Instance.runtime == runtime, Instance.runtime.is_(None), Instance.runtime == ""),
            )
            .distinct()
        )).scalars().all()

        if rows:
            sorted_tags = sorted(set(rows), key=_version_key, reverse=True)
            for idx, image_tag in enumerate(sorted_tags):
                stripped = image_tag.lstrip("v") if image_tag.startswith("v") else image_tag
                db.add(EngineVersion(
                    runtime=runtime,
                    version=stripped,
                    image_tag=image_tag,
                    status="published",
                    is_default=(idx == 0),
                ))
            await db.flush()
            logger.info("引擎版本目录自动回填完成：runtime=%s，count=%d", runtime, len(sorted_tags))
        return

    default_row = await db.execute(
        select(EngineVersion).where(
            EngineVersion.runtime == runtime,
            EngineVersion.is_default.is_(True),
            not_deleted(EngineVersion),
        )
    )
    if default_row.scalar_one_or_none() is not None:
        return

    latest_published = await db.execute(
        select(EngineVersion)
        .where(
            EngineVersion.runtime == runtime,
            EngineVersion.status == "published",
            not_deleted(EngineVersion),
        )
        .order_by(EngineVersion.created_at.desc())
        .limit(1)
    )
    candidate = latest_published.scalar_one_or_none()
    if candidate is None:
        return
    candidate.is_default = True
    await db.flush()
    logger.warning("引擎版本目录缺失默认版本，已自动修复：runtime=%s image_tag=%s", runtime, candidate.image_tag)


async def list_published(runtime: str, db: AsyncSession) -> list[EngineVersion]:
    await _ensure_catalog_initialized(runtime, db)
    result = await db.execute(
        select(EngineVersion)
        .where(
            EngineVersion.runtime == runtime,
            EngineVersion.status == "published",
            not_deleted(EngineVersion),
        )
        .order_by(EngineVersion.created_at.desc())
    )
    return list(result.scalars().all())


async def get_default(runtime: str, db: AsyncSession) -> EngineVersion | None:
    await _ensure_catalog_initialized(runtime, db)
    result = await db.execute(
        select(EngineVersion).where(
            EngineVersion.runtime == runtime,
            EngineVersion.is_default.is_(True),
            not_deleted(EngineVersion),
        )
    )
    return result.scalar_one_or_none()


async def publish(
    runtime: str,
    version: str,
    image_tag: str,
    release_notes: str | None,
    user_id: str,
    db: AsyncSession,
) -> EngineVersion:
    existing = await db.execute(
        select(EngineVersion).where(
            EngineVersion.runtime == runtime,
            EngineVersion.version == version,
            not_deleted(EngineVersion),
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(
            f"版本 {version} 已存在", "errors.engine_version.already_exists"
        )

    ev = EngineVersion(
        runtime=runtime,
        version=version,
        image_tag=image_tag,
        status="published",
        release_notes=release_notes,
        published_by=user_id,
    )
    db.add(ev)
    await db.flush()
    return ev


async def set_default(version_id: str, db: AsyncSession) -> EngineVersion:
    result = await db.execute(
        select(EngineVersion).where(
            EngineVersion.id == version_id,
            not_deleted(EngineVersion),
        )
    )
    ev = result.scalar_one_or_none()
    if not ev:
        raise NotFoundError("版本不存在", "errors.engine_version.not_found")

    await db.execute(
        update(EngineVersion)
        .where(
            EngineVersion.runtime == ev.runtime,
            EngineVersion.is_default.is_(True),
            not_deleted(EngineVersion),
        )
        .values(is_default=False)
    )
    ev.is_default = True
    await db.flush()
    return ev


async def update_notes(version_id: str, notes: str, db: AsyncSession) -> EngineVersion:
    result = await db.execute(
        select(EngineVersion).where(
            EngineVersion.id == version_id,
            not_deleted(EngineVersion),
        )
    )
    ev = result.scalar_one_or_none()
    if not ev:
        raise NotFoundError("版本不存在", "errors.engine_version.not_found")
    ev.release_notes = notes
    await db.flush()
    return ev


async def deprecate(version_id: str, db: AsyncSession) -> EngineVersion:
    result = await db.execute(
        select(EngineVersion).where(
            EngineVersion.id == version_id,
            not_deleted(EngineVersion),
        )
    )
    ev = result.scalar_one_or_none()
    if not ev:
        raise NotFoundError("版本不存在", "errors.engine_version.not_found")
    if ev.is_default:
        raise BadRequestError(
            "不能废弃当前默认版本，请先设置其他版本为默认",
            "errors.engine_version.cannot_deprecate_default",
        )
    ev.status = "deprecated"
    await db.flush()
    return ev


async def delete(version_id: str, db: AsyncSession) -> None:
    result = await db.execute(
        select(EngineVersion).where(
            EngineVersion.id == version_id,
            not_deleted(EngineVersion),
        )
    )
    ev = result.scalar_one_or_none()
    if not ev:
        raise NotFoundError("版本不存在", "errors.engine_version.not_found")
    if ev.is_default:
        raise BadRequestError(
            "不能删除当前默认版本，请先设置其他版本为默认",
            "errors.engine_version.cannot_delete_default",
        )
    ev.soft_delete()
    await db.flush()
