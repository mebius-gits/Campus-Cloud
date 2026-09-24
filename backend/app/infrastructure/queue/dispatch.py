"""任務入列：建立 TaskRecord 並送進 arq 隊列。

``enqueue_task`` 給 async 路由／服務用；``enqueue_task_sync`` 給跑在
threadpool 的 sync 路由用（把 arq 的 async enqueue 丟回主 event loop 等結果）。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from sqlmodel import Session

from app.features.ai.config import settings
from app.models import TaskRecord, TaskRecordStatus
from app.repositories import task_record as task_record_repo

from .arq_client import QUEUE_NAME, get_arq_pool

logger = logging.getLogger(__name__)

# sync 路由等 enqueue 完成的上限：Redis 正常時是毫秒級，逾時代表 Redis 有問題
ENQUEUE_SYNC_TIMEOUT_SECONDS = 10.0


async def enqueue_task(
    *,
    session: Session,
    task_type: str,
    user_id: uuid.UUID,
    payload: dict[str, Any],
    template_id: uuid.UUID | None = None,
) -> TaskRecord:
    """建立 TaskRecord 並入列；入列失敗時記錄 failed 後拋出。"""
    record = task_record_repo.create_task_record(
        session=session,
        task_type=task_type,
        user_id=user_id,
        payload=payload,
        template_id=template_id,
    )
    await _dispatch_record(
        session=session, record=record, task_type=task_type, payload=payload
    )
    return record


def enqueue_task_sync(
    *,
    session: Session,
    task_type: str,
    user_id: uuid.UUID,
    payload: dict[str, Any],
    template_id: uuid.UUID | None = None,
) -> TaskRecord:
    """``enqueue_task`` 的 sync 版：從 threadpool（sync 路由）呼叫。

    TaskRecord 在呼叫端執行緒寫入；只有 arq 的 enqueue 需要 event loop，
    透過 ``run_coroutine_threadsafe`` 丟回 lifespan 綁定的主 loop 等待完成。
    在 event loop 執行緒上呼叫會直接拋錯（那裡應該 await ``enqueue_task``）。
    """
    from app.infrastructure.worker import (
        get_runner,  # noqa: PLC0415 — 避免 import cycle
    )

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError(
            "enqueue_task_sync called on the event loop thread; await enqueue_task instead"
        )

    record = task_record_repo.create_task_record(
        session=session,
        task_type=task_type,
        user_id=user_id,
        payload=payload,
        template_id=template_id,
    )
    coro = _dispatch_record(
        session=session, record=record, task_type=task_type, payload=payload
    )
    runner = get_runner()
    loop = runner.bound_loop() if runner is not None else None
    if loop is None or loop.is_closed():
        # 沒有 lifespan（單元測試、CLI 腳本）：就地跑一個 loop 完成入列
        asyncio.run(coro)
        return record
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    future.result(timeout=ENQUEUE_SYNC_TIMEOUT_SECONDS)
    return record


async def _dispatch_record(
    *,
    session: Session,
    record: TaskRecord,
    task_type: str,
    payload: dict[str, Any],
) -> None:
    try:
        if not settings.redis_enabled:
            # Import task modules lazily so their decorators populate the
            # registry without creating an import cycle during app startup.
            from app.infrastructure.worker import submit  # noqa: PLC0415

            from .modules import import_task_modules  # noqa: PLC0415
            from .registry import run_registered_task_locally  # noqa: PLC0415

            import_task_modules()
            submitted_id = submit(
                run_registered_task_locally(
                    task_type,
                    str(record.id),
                    payload,
                ),
                name=task_type,
                task_id=str(record.id),
            )
            if not submitted_id:
                raise RuntimeError("local background runner is not available")
            return

        pool = await get_arq_pool()
        job = await pool.enqueue_job(
            task_type,
            str(record.id),
            payload,
            _job_id=str(record.id),
            _queue_name=QUEUE_NAME,
        )
        if job is None:
            raise RuntimeError(f"duplicate job id {record.id}")
    except Exception as exc:
        logger.exception("enqueue task '%s' failed", task_type)
        task_record_repo.mark_task_finished(
            session=session,
            task_id=record.id,
            status=TaskRecordStatus.failed,
            error=f"入列失敗: {exc}",
        )
        raise
