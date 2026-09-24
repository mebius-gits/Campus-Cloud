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
    job_id: str | None = None,
) -> TaskRecord | None:
    """建立 TaskRecord 並入列；入列失敗時記錄 failed 後拋出。

    ``job_id`` 指定 arq job id 以做跨行程去重：同 id 的 job 還在排隊或執行中
    時不會再入列，剛建立的 TaskRecord 會被刪掉並回傳 None。未指定時以
    TaskRecord id 當 job id（永不重複）。
    """
    record = task_record_repo.create_task_record(
        session=session,
        task_type=task_type,
        user_id=user_id,
        payload=payload,
        template_id=template_id,
    )
    if await _dispatch_record(
        session=session, record=record, task_type=task_type, payload=payload,
        job_id=job_id,
    ):
        return record
    return None


def enqueue_task_sync(
    *,
    session: Session,
    task_type: str,
    user_id: uuid.UUID,
    payload: dict[str, Any],
    template_id: uuid.UUID | None = None,
    job_id: str | None = None,
) -> TaskRecord | None:
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
        session=session, record=record, task_type=task_type, payload=payload,
        job_id=job_id,
    )
    runner = get_runner()
    loop = runner.bound_loop() if runner is not None else None
    if loop is None or loop.is_closed():
        # 沒有 lifespan（單元測試、CLI 腳本）：就地跑一個 loop 完成入列
        dispatched = asyncio.run(coro)
    else:
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        dispatched = future.result(timeout=ENQUEUE_SYNC_TIMEOUT_SECONDS)
    return record if dispatched else None


def _discard_duplicate_record(*, session: Session, record: TaskRecord) -> None:
    """同 job id 已在隊列中：這筆 TaskRecord 不會有人執行，直接刪掉。"""
    session.delete(record)
    session.commit()


async def _dispatch_record(
    *,
    session: Session,
    record: TaskRecord,
    task_type: str,
    payload: dict[str, Any],
    job_id: str | None = None,
) -> bool:
    """把 record 送進隊列；回傳 False 代表被 ``job_id`` 去重擋下（record 已刪）。"""
    try:
        if not settings.redis_enabled:
            # Import task modules lazily so their decorators populate the
            # registry without creating an import cycle during app startup.
            from app.infrastructure.worker import is_active, submit  # noqa: PLC0415

            from .modules import import_task_modules  # noqa: PLC0415
            from .registry import run_registered_task_locally  # noqa: PLC0415

            import_task_modules()
            local_task_id = job_id or str(record.id)
            if job_id is not None and is_active(local_task_id):
                _discard_duplicate_record(session=session, record=record)
                return False
            submitted_id = submit(
                run_registered_task_locally(
                    task_type,
                    str(record.id),
                    payload,
                ),
                name=task_type,
                task_id=local_task_id,
            )

            if not submitted_id:
                raise RuntimeError("local background runner is not available")
            return True

        pool = await get_arq_pool()
        job = await pool.enqueue_job(
            task_type,
            str(record.id),
            payload,
            _job_id=job_id or str(record.id),
            _queue_name=QUEUE_NAME,
        )
        if job is None:
            if job_id is not None:
                logger.info(
                    "queue task '%s' job_id=%s already queued; skipping duplicate",
                    task_type, job_id,
                )
                _discard_duplicate_record(session=session, record=record)
                return False
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
    return True

