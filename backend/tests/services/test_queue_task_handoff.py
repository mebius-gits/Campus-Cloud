"""重工作改走 arq：入列 payload 與 worker handler 解包必須對得上。"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.models import DeletionRequest, DeletionRequestStatus
from app.services.proxmox import provisioning_service
from app.services.resource import deletion_service, reset_service
from app.services.vm import batch_provision_service


@pytest.fixture(scope="session")
def _seed_first_superuser() -> None:
    """純單元測試，不需要測試資料庫。"""


class _Session:
    def add(self, obj: Any) -> None:
        """測試替身。"""

    def commit(self) -> None:
        """測試替身。"""


def _capture_enqueue(monkeypatch: pytest.MonkeyPatch, module: Any) -> list[dict]:
    calls: list[dict] = []

    def fake_enqueue(**kwargs: Any):
        calls.append(kwargs)
        return SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(module, "enqueue_task_sync", fake_enqueue)
    return calls


# ─── 一鍵重置 ─────────────────────────────────────────────────────────────────


def test_start_reset_enqueues_reset_task(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(id=uuid.uuid4())
    monkeypatch.setattr(reset_service, "_has_init_snapshot", lambda *_: True)
    monkeypatch.setattr(reset_service.audit_service, "log_action", lambda **_: None)
    calls = _capture_enqueue(monkeypatch, reset_service)

    task_id = reset_service.start_reset(
        _Session(), vmid=101, resource_info={"node": "pve1", "type": "lxc"}, user=user
    )

    assert uuid.UUID(task_id)
    assert len(calls) == 1
    assert calls[0]["task_type"] == reset_service.TASK_RESET
    assert calls[0]["user_id"] == user.id
    assert calls[0]["payload"] == {
        "vmid": 101,
        "node": "pve1",
        "rtype": "lxc",
        "user_id": str(user.id),
    }


def test_run_reset_task_unpacks_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple] = []
    monkeypatch.setattr(
        reset_service, "_run_reset", lambda *args: seen.append(args)
    )
    user_id = uuid.uuid4()

    result = reset_service.run_reset_task(
        uuid.uuid4(),
        {"vmid": "101", "node": "pve1", "rtype": "qemu", "user_id": str(user_id)},
    )

    assert seen == [(101, "pve1", "qemu", user_id)]
    assert result == {"vmid": 101}


# ─── 批次佈建 ─────────────────────────────────────────────────────────────────


def test_approve_batch_job_enqueues_instead_of_threading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id, reviewer = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(
        batch_provision_service.bp_repo, "get_job", lambda **_: SimpleNamespace(id=job_id)
    )
    monkeypatch.setattr(
        batch_provision_service.bp_repo,
        "transition_pending_review",
        lambda **_: SimpleNamespace(id=job_id),
    )
    calls = _capture_enqueue(monkeypatch, batch_provision_service)

    batch_provision_service.approve_batch_job(
        session=_Session(), job_id=job_id, reviewer_id=reviewer
    )

    assert calls == [
        {
            "session": calls[0]["session"],
            "task_type": batch_provision_service.TASK_RUN_BATCH_JOB,
            "user_id": reviewer,
            "payload": {"job_id": str(job_id)},
        }
    ]


def test_run_batch_job_task_runs_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    ran: list[uuid.UUID] = []
    monkeypatch.setattr(batch_provision_service, "_run_queue", ran.append)
    job_id = uuid.uuid4()

    result = batch_provision_service.run_batch_job_task(
        uuid.uuid4(), {"job_id": str(job_id)}
    )

    assert ran == [job_id]
    assert result == {"job_id": str(job_id)}


# ─── 管理員直接建 VM ──────────────────────────────────────────────────────────


def test_admin_create_vm_task_rebuilds_request(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_create_vm(*, session, vm_data, user_id):  # noqa: ARG001
        seen["vm_data"] = vm_data
        seen["user_id"] = user_id
        return SimpleNamespace(vmid=250, upid="UPID:pve1:1")

    monkeypatch.setattr(provisioning_service, "create_vm", fake_create_vm)
    user_id = uuid.uuid4()
    payload = {
        "vm_data": {
            "hostname": "lab-01",
            "template_id": 9000,
            "username": "student",
            "password": "secret-pass",
            "environment_type": "generic",
        },
        "user_id": str(user_id),
    }

    result = provisioning_service.run_admin_create_vm_task(uuid.uuid4(), payload)

    assert seen["vm_data"].hostname == "lab-01"
    assert seen["vm_data"].template_id == 9000
    assert seen["user_id"] == user_id
    assert result == {"vmid": 250, "upid": "UPID:pve1:1"}


# ─── 刪除請求認領 ─────────────────────────────────────────────────────────────


class _ClaimSession:
    """只模擬認領那一段：條件式 UPDATE 的 rowcount 由測試決定。"""

    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount
        self.committed = 0
        self.exec_calls = 0

    def execute(self, _stmt: Any) -> SimpleNamespace:
        return SimpleNamespace(rowcount=self.rowcount)

    def commit(self) -> None:
        self.committed += 1

    def refresh(self, _obj: Any) -> None:
        """測試替身。"""

    def exec(self, _stmt: Any) -> Any:
        self.exec_calls += 1
        raise RuntimeError("continued past claim")


def _pending_request() -> DeletionRequest:
    return DeletionRequest(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        vmid=150,
        name="ct-150",
        node="pve1",
        resource_type="lxc",
        status=DeletionRequestStatus.pending,
    )


def test_execute_deletion_skips_when_another_worker_claimed_first() -> None:
    session = _ClaimSession(rowcount=0)

    deletion_service._execute_deletion(session, _pending_request())  # type: ignore[arg-type]

    assert session.committed == 1
    assert session.exec_calls == 0


def test_execute_deletion_continues_after_winning_claim() -> None:
    session = _ClaimSession(rowcount=1)

    with pytest.raises(RuntimeError, match="continued past claim"):
        deletion_service._execute_deletion(session, _pending_request())  # type: ignore[arg-type]

    assert session.exec_calls == 1
