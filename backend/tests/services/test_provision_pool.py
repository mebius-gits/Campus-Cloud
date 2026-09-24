"""克隆 fan-out：API 端入列（job id 去重）、worker 端 semaphore 限流。"""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.models import VMProvisioningStatus
from app.services.scheduling import provision_pool


@pytest.fixture(scope="session")
def _seed_first_superuser() -> None:
    """純單元測試，不需要測試資料庫。"""


@pytest.fixture(autouse=True)
def _fresh_semaphore():
    provision_pool.reset_provision_semaphore()
    yield
    provision_pool.reset_provision_semaphore()


class _Tracker:
    def __init__(self, delay: float = 0.03) -> None:
        self.delay = delay
        self.in_flight = 0
        self.peak = 0
        self.calls: list[uuid.UUID] = []

    async def fake_execute(self, request_id: uuid.UUID) -> bool:
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        try:
            await asyncio.sleep(self.delay)
            self.calls.append(request_id)
            return True
        finally:
            self.in_flight -= 1


# ─── API 端：入列 ─────────────────────────────────────────────────────────────


def test_submit_provision_enqueues_with_stable_job_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []
    record = SimpleNamespace(id=uuid.uuid4())
    monkeypatch.setattr(
        provision_pool, "enqueue_task_sync", lambda **kw: calls.append(kw) or record
    )
    request_id, user_id = uuid.uuid4(), uuid.uuid4()

    result = provision_pool.submit_provision(
        object(),  # type: ignore[arg-type]
        request_id=request_id,
        user_id=user_id,
        concurrency=4,
    )

    assert result is record
    assert calls[0]["task_type"] == provision_pool.TASK_PROVISION
    assert calls[0]["user_id"] == user_id
    assert calls[0]["payload"] == {"request_id": str(request_id), "concurrency": 4}
    # 同一張單所有入列路徑共用這個 job id，排隊中／執行中不會再入列
    assert calls[0]["job_id"] == f"vm_request:{request_id}"


# ─── worker 端：限流與結果 ────────────────────────────────────────────────────


async def test_worker_concurrency_capped_by_semaphore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracker = _Tracker()
    monkeypatch.setattr(provision_pool, "_execute_provision", tracker.fake_execute)
    monkeypatch.setattr(provision_pool, "_provisioning_failure", lambda _rid: None)

    ids = [uuid.uuid4() for _ in range(20)]
    results = await asyncio.gather(
        *(provision_pool.run_provision_job(rid, concurrency=4) for rid in ids)
    )

    assert tracker.peak <= 4
    assert sorted(map(str, tracker.calls)) == sorted(map(str, ids))
    assert all(r["started"] is True for r in results)


async def test_worker_raises_when_request_ends_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_execute(_request_id: uuid.UUID) -> bool:
        return False

    monkeypatch.setattr(provision_pool, "_execute_provision", fake_execute)
    monkeypatch.setattr(
        provision_pool, "_provisioning_failure", lambda _rid: "clone exploded"
    )

    with pytest.raises(RuntimeError, match="clone exploded"):
        await provision_pool.run_provision_job(uuid.uuid4(), concurrency=1)


def test_provisioning_failure_reads_request_state(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.repositories import vm_request as vm_request_repo

    failed = SimpleNamespace(
        vmid=None,
        provisioning_status=VMProvisioningStatus.failed,
        provisioning_error="no space left",
    )
    monkeypatch.setattr(
        vm_request_repo, "get_vm_request_by_id", lambda **_kw: failed
    )

    class _Session:
        def __init__(self, _engine: Any) -> None:
            """測試替身。"""

        def __enter__(self) -> _Session:
            return self

        def __exit__(self, *_exc: Any) -> None:
            """測試替身。"""

    monkeypatch.setattr(provision_pool, "Session", _Session)

    assert provision_pool._provisioning_failure(uuid.uuid4()) == "no space left"

    failed.provisioning_status = VMProvisioningStatus.completed
    failed.vmid = 150
    assert provision_pool._provisioning_failure(uuid.uuid4()) is None


async def test_semaphore_rebuilt_on_size_change() -> None:
    sem_a = provision_pool.get_provision_semaphore(2)
    sem_a2 = provision_pool.get_provision_semaphore(2)
    sem_b = provision_pool.get_provision_semaphore(6)
    assert sem_a is sem_a2
    assert sem_b is not sem_a
