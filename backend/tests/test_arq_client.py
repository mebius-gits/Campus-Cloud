import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import settings as core_settings
from app.infrastructure import worker
from app.infrastructure.queue import arq_client, dispatch, registry


@pytest.fixture(scope="session")
def _seed_first_superuser() -> None:
    """This unit-test module does not require the external test database."""


@pytest.fixture(autouse=True)
def reset_arq_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(arq_client, "_pool", None)


async def test_init_arq_pool_skips_connection_when_redis_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_pool = AsyncMock()
    # redis_enabled 已改為代理 core settings 的唯讀 property
    monkeypatch.setattr(core_settings, "REDIS_ENABLED", False)
    monkeypatch.setattr(arq_client, "create_pool", create_pool)

    await arq_client.init_arq_pool()

    create_pool.assert_not_awaited()
    assert arq_client._pool is None


async def test_get_arq_pool_does_not_connect_when_redis_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_pool = AsyncMock()
    # redis_enabled 已改為代理 core settings 的唯讀 property
    monkeypatch.setattr(core_settings, "REDIS_ENABLED", False)
    monkeypatch.setattr(arq_client, "create_pool", create_pool)

    with pytest.raises(RuntimeError, match="REDIS_ENABLED=false"):
        await arq_client.get_arq_pool()

    create_pool.assert_not_awaited()


async def test_init_arq_pool_connects_when_redis_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = AsyncMock()
    create_pool = AsyncMock(return_value=pool)
    monkeypatch.setattr(core_settings, "REDIS_ENABLED", True)
    monkeypatch.setattr(arq_client, "create_pool", create_pool)

    await arq_client.init_arq_pool()

    create_pool.assert_awaited_once()
    assert arq_client._pool is pool


async def test_enqueue_uses_local_runner_when_redis_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = SimpleNamespace(id=uuid.uuid4())
    scheduled: list[object] = []
    executed: list[tuple[str, str, dict[str, object]]] = []

    monkeypatch.setattr(core_settings, "REDIS_ENABLED", False)
    monkeypatch.setattr(
        dispatch.task_record_repo,
        "create_task_record",
        lambda **_: record,
    )

    async def fake_run(
        name: str,
        record_id: str,
        payload: dict[str, object],
    ) -> None:
        executed.append((name, record_id, payload))

    def fake_submit(coro: object, **kwargs: object) -> str:
        scheduled.append(coro)
        return str(kwargs["task_id"])

    monkeypatch.setattr(registry, "run_registered_task_locally", fake_run)
    monkeypatch.setattr(worker, "submit", fake_submit)

    result = await dispatch.enqueue_task(
        session=object(),  # type: ignore[arg-type]
        task_type="template.convert",
        user_id=uuid.uuid4(),
        template_id=uuid.uuid4(),
        payload={"vmid": 101},
    )

    assert result is record
    assert len(scheduled) == 1
    await asyncio.wait_for(scheduled[0], timeout=5)  # type: ignore[misc]
    assert executed == [
        ("template.convert", str(record.id), {"vmid": 101})
    ]


def test_enqueue_task_sync_runs_without_bound_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """沒有 lifespan（CLI／單元測試）時就地開 loop 完成入列。"""
    record = SimpleNamespace(id=uuid.uuid4())
    executed: list[tuple[str, str, dict[str, object]]] = []

    monkeypatch.setattr(core_settings, "REDIS_ENABLED", False)
    monkeypatch.setattr(
        dispatch.task_record_repo, "create_task_record", lambda **_: record
    )
    monkeypatch.setattr(worker, "get_runner", lambda: None)

    async def fake_run(name: str, record_id: str, payload: dict[str, object]) -> None:
        executed.append((name, record_id, payload))

    def fake_submit(coro: object, **kwargs: object) -> str:
        coro.close()  # type: ignore[attr-defined]
        executed.append(("submitted", str(kwargs["task_id"]), {}))
        return str(kwargs["task_id"])

    monkeypatch.setattr(registry, "run_registered_task_locally", fake_run)
    monkeypatch.setattr(worker, "submit", fake_submit)

    result = dispatch.enqueue_task_sync(
        session=object(),  # type: ignore[arg-type]
        task_type="resource.reset",
        user_id=uuid.uuid4(),
        payload={"vmid": 101},
    )

    assert result is record
    assert executed == [("submitted", str(record.id), {})]


def test_enqueue_task_sync_uses_bound_loop_from_worker_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """sync 路由（threadpool）呼叫時，enqueue 要跑在 lifespan 綁定的主 loop 上。"""
    record = SimpleNamespace(id=uuid.uuid4())
    seen_loops: list[asyncio.AbstractEventLoop] = []

    monkeypatch.setattr(
        dispatch.task_record_repo, "create_task_record", lambda **_: record
    )

    async def fake_dispatch(**_kwargs: object) -> None:
        seen_loops.append(asyncio.get_running_loop())

    monkeypatch.setattr(dispatch, "_dispatch_record", fake_dispatch)

    async def main() -> None:
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(
            worker, "get_runner", lambda: SimpleNamespace(bound_loop=lambda: loop)
        )
        result = await asyncio.to_thread(
            dispatch.enqueue_task_sync,
            session=object(),  # type: ignore[arg-type]
            task_type="resource.reset",
            user_id=uuid.uuid4(),
            payload={},
        )
        assert result is record
        assert seen_loops == [loop]

    asyncio.run(main())


async def test_enqueue_task_sync_refuses_event_loop_thread() -> None:
    with pytest.raises(RuntimeError, match="await enqueue_task"):
        dispatch.enqueue_task_sync(
            session=object(),  # type: ignore[arg-type]
            task_type="resource.reset",
            user_id=uuid.uuid4(),
            payload={},
        )
