import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.security import encrypt_value
from app.ai.pve_advisor.schemas import NodeCapacity
from app.exceptions import BadRequestError, ProxmoxError, ProvisioningError
from app.models import (
    ProxmoxConfig,
    ProxmoxNode,
    ProxmoxStorage,
    Resource,
    SpecChangeRequest,
    SpecChangeRequestStatus,
    SpecChangeType,
    User,
    UserRole,
    VMMigrationStatus,
    VMRequest,
    VMRequestStatus,
)
from app.repositories import user as user_repo
from app.schemas import (
    SpecChangeRequestReview,
    UserCreate,
    VMCreateRequest,
    VMRequestCreate,
    VMRequestReview,
)
from app.services import (
    provisioning_service,
    proxmox_service,
    spec_change_service,
    user_service,
    vm_request_placement_service,
    vm_request_schedule_service,
    vm_request_service,
)


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _create_user(
    session: Session,
    *,
    is_superuser: bool = False,
    role: UserRole | None = None,
) -> User:
    user = user_repo.create_user(
        session=session,
        user_create=UserCreate(
            email=f"{'admin' if is_superuser else 'user'}-{datetime.now(timezone.utc).timestamp()}@example.com",
            password="strongpass123",
            role=role or (UserRole.admin if is_superuser else UserRole.student),
            is_superuser=is_superuser,
        ),
    )
    session.commit()
    session.refresh(user)
    return user


def _seed_managed_storage(
    session: Session,
    *,
    node_name: str,
    storage: str,
    speed_tier: str,
    user_priority: int,
    can_vm: bool = True,
    can_lxc: bool = True,
    avail_gb: float = 200.0,
    total_gb: float = 400.0,
) -> None:
    session.add(
        ProxmoxStorage(
            node_name=node_name,
            storage=storage,
            storage_type="dir",
            total_gb=total_gb,
            used_gb=max(total_gb - avail_gb, 0.0),
            avail_gb=avail_gb,
            can_vm=can_vm,
            can_lxc=can_lxc,
            can_iso=False,
            can_backup=False,
            is_shared=False,
            active=True,
            enabled=True,
            speed_tier=speed_tier,
            user_priority=user_priority,
        )
    )


def test_vm_request_create_preserves_environment_type(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _create_user(db)
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(
        "app.services.vm_request_service.vm_request_availability_service.validate_request_window",
        lambda **kwargs: None,
    )
    request_in = VMRequestCreate(
        reason="Need a custom environment for backend testing",
        resource_type="vm",
        hostname="env-check",
        cores=2,
        memory=2048,
        password="strongpass123",
        storage="fast-ssd",
        environment_type="ML Lab",
        template_id=9000,
        disk_size=32,
        username="student",
        start_at=now + timedelta(hours=1),
        end_at=now + timedelta(hours=3),
    )

    result = vm_request_service.create(session=db, request_in=request_in, user=user)

    db.expire_all()
    saved = db.exec(select(VMRequest).where(VMRequest.id == result.id)).first()
    assert saved is not None
    assert result.environment_type == "ML Lab"
    assert saved.environment_type == "ML Lab"
    assert saved.storage == "fast-ssd"


def test_vm_request_create_rejects_unavailable_window(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _create_user(db)
    now = datetime.now(timezone.utc)
    request_in = VMRequestCreate(
        reason="Need a custom environment for backend testing",
        resource_type="vm",
        hostname="env-check-blocked",
        cores=2,
        memory=2048,
        password="strongpass123",
        storage="fast-ssd",
        environment_type="ML Lab",
        template_id=9000,
        disk_size=32,
        username="student",
        start_at=now + timedelta(hours=1),
        end_at=now + timedelta(hours=3),
    )

    monkeypatch.setattr(
        "app.services.vm_request_service.vm_request_availability_service.validate_request_window",
        lambda **kwargs: (_ for _ in ()).throw(
            BadRequestError("No node is available for the requested time window.")
        ),
    )

    with pytest.raises(BadRequestError):
        vm_request_service.create(session=db, request_in=request_in, user=user)


def test_vm_request_review_rolls_back_and_cleans_up_on_failure(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _create_user(db)
    reviewer = _create_user(db, is_superuser=True)
    now = datetime.now(timezone.utc)
    request = VMRequest(
        user_id=user.id,
        reason="Need a VM for rollback coverage",
        resource_type="vm",
        hostname="rollback-vm",
        cores=2,
        memory=2048,
        password=encrypt_value("strongpass123"),
        storage="local-lvm",
        environment_type="Rollback Test",
        template_id=123,
        disk_size=20,
        username="student",
        status=VMRequestStatus.pending,
        start_at=now + timedelta(hours=2),
        end_at=now + timedelta(hours=4),
        created_at=now,
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    monkeypatch.setattr(
        "app.services.vm_request_service.vm_request_placement_service.rebuild_reserved_assignments",
        lambda **kwargs: {
            request.id: SimpleNamespace(
                node="pve-a",
                strategy="priority_dominant_share",
                plan=SimpleNamespace(feasible=True),
            )
        },
    )

    def _raise_audit(*args, **kwargs):
        raise RuntimeError("audit failure")

    monkeypatch.setattr(
        "app.services.vm_request_service.audit_service.log_action",
        _raise_audit,
    )

    with pytest.raises(ProvisioningError):
        vm_request_service.review(
            session=db,
            request_id=request.id,
            review_data=VMRequestReview(status=VMRequestStatus.approved),
            reviewer=reviewer,
        )

    db.expire_all()
    refreshed = db.exec(select(VMRequest).where(VMRequest.id == request.id)).first()
    assert refreshed is not None
    assert refreshed.status == VMRequestStatus.pending
    assert refreshed.vmid is None
    assert refreshed.reviewer_id is None
    assert refreshed.assigned_node is None
    assert refreshed.placement_strategy_used is None


def test_vm_request_review_locks_overlapping_requests(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _create_user(db)
    reviewer = _create_user(db, is_superuser=True)
    now = datetime.now(timezone.utc)
    request = VMRequest(
        user_id=user.id,
        reason="Need a VM for scheduled class usage",
        resource_type="vm",
        hostname="lock-window-vm",
        cores=2,
        memory=2048,
        password=encrypt_value("strongpass123"),
        storage="local-lvm",
        environment_type="Lock Window Test",
        template_id=123,
        disk_size=20,
        username="student",
        status=VMRequestStatus.pending,
        start_at=now + timedelta(hours=2),
        end_at=now + timedelta(hours=4),
        created_at=now,
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    captured: dict[str, datetime] = {}

    def _lock_window(**kwargs):
        captured["start_at"] = kwargs["window_start"]
        captured["end_at"] = kwargs["window_end"]
        return [request]

    monkeypatch.setattr(
        "app.services.vm_request_service.vm_request_repo.lock_overlapping_vm_requests_for_window",
        _lock_window,
    )
    monkeypatch.setattr(
        "app.services.vm_request_service.audit_service.log_action",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.vm_request_service.vm_request_placement_service.rebuild_reserved_assignments",
        lambda **kwargs: {
            request.id: SimpleNamespace(
                node="pve-a",
                strategy="priority_dominant_share",
                plan=SimpleNamespace(feasible=True),
            )
        },
    )

    vm_request_service.review(
        session=db,
        request_id=request.id,
        review_data=VMRequestReview(status=VMRequestStatus.approved),
        reviewer=reviewer,
    )

    assert captured["start_at"] == request.start_at.replace(tzinfo=timezone.utc)
    assert captured["end_at"] == request.end_at.replace(tzinfo=timezone.utc)


def test_vm_request_review_assigns_reserved_node(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _create_user(db)
    reviewer = _create_user(db, is_superuser=True)
    now = datetime.now(timezone.utc)
    request = VMRequest(
        user_id=user.id,
        reason="Need a VM for scheduled class usage",
        resource_type="vm",
        hostname="reserved-node-vm",
        cores=2,
        memory=2048,
        password=encrypt_value("strongpass123"),
        storage="local-lvm",
        environment_type="Reserved Node Test",
        template_id=123,
        disk_size=20,
        username="student",
        status=VMRequestStatus.pending,
        start_at=now + timedelta(hours=2),
        end_at=now + timedelta(hours=4),
        created_at=now,
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    monkeypatch.setattr(
        "app.services.vm_request_service.audit_service.log_action",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.vm_request_service.vm_request_placement_service.rebuild_reserved_assignments",
        lambda **kwargs: {
            request.id: SimpleNamespace(
                node="pve-a",
                strategy="priority_dominant_share",
                plan=SimpleNamespace(feasible=True),
            )
        },
    )

    result = vm_request_service.review(
        session=db,
        request_id=request.id,
        review_data=VMRequestReview(status=VMRequestStatus.approved),
        reviewer=reviewer,
    )

    db.expire_all()
    refreshed = db.exec(select(VMRequest).where(VMRequest.id == request.id)).first()
    assert refreshed is not None
    assert result.status == VMRequestStatus.approved
    assert result.assigned_node == "pve-a"
    assert result.placement_strategy_used == "priority_dominant_share"
    assert refreshed.status == VMRequestStatus.approved
    assert refreshed.assigned_node == "pve-a"
    assert refreshed.placement_strategy_used == "priority_dominant_share"


def test_vm_request_review_context_includes_runtime_and_projection(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _create_user(db)
    reviewer = _create_user(db, is_superuser=True)
    now = datetime.now(timezone.utc)
    approved = VMRequest(
        user_id=user.id,
        reason="Approved overlap request",
        resource_type="vm",
        hostname="approved-overlap",
        cores=2,
        memory=2048,
        password=encrypt_value("strongpass123"),
        storage="local-lvm",
        environment_type="Review Context",
        template_id=200,
        disk_size=20,
        username="student",
        status=VMRequestStatus.approved,
        start_at=now + timedelta(hours=1),
        end_at=now + timedelta(hours=3),
        vmid=801,
        assigned_node="pve-a",
        desired_node="pve-a",
        actual_node="pve-a",
        created_at=now - timedelta(minutes=5),
    )
    pending = VMRequest(
        user_id=user.id,
        reason="Pending request for review context",
        resource_type="vm",
        hostname="pending-review",
        cores=2,
        memory=2048,
        password=encrypt_value("strongpass123"),
        storage="local-lvm",
        environment_type="Review Context",
        template_id=201,
        disk_size=20,
        username="student",
        status=VMRequestStatus.pending,
        start_at=now + timedelta(hours=1),
        end_at=now + timedelta(hours=3),
        created_at=now,
    )
    db.add(approved)
    db.add(pending)
    db.commit()
    db.refresh(approved)
    db.refresh(pending)

    monkeypatch.setattr(
        "app.services.vm_request_service.proxmox_service.list_nodes",
        lambda: [
            {"node": "pve-a"},
            {"node": "pve-b"},
            {"node": "pve-c"},
            {"node": "pve-d"},
        ],
    )
    monkeypatch.setattr(
        "app.services.vm_request_service.proxmox_service.list_all_resources",
        lambda: [
            {
                "vmid": 801,
                "name": "approved-overlap",
                "node": "pve-a",
                "type": "qemu",
                "status": "running",
                "pool": "CampusCloud",
            }
        ],
    )
    monkeypatch.setattr(
        "app.services.vm_request_service.vm_request_repo.list_active_approved_vm_requests",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "app.services.vm_request_service.vm_request_placement_service.rebuild_reserved_assignments",
        lambda **kwargs: {
            approved.id: SimpleNamespace(
                node="pve-a",
                strategy="priority_dominant_share",
                plan=SimpleNamespace(feasible=True, summary="approved summary", warnings=[]),
            ),
            pending.id: SimpleNamespace(
                node="pve-b",
                strategy="priority_dominant_share",
                plan=SimpleNamespace(
                    feasible=True,
                    summary="pending summary",
                    warnings=["rebalance warning"],
                ),
            ),
        },
    )

    context = vm_request_service.get_review_context(
        session=db,
        request_id=pending.id,
        current_user=reviewer,
    )

    assert context.projected_node == "pve-b"
    assert context.placement_strategy == "priority_dominant_share"
    assert context.summary == "pending summary"
    assert context.warnings == ["rebalance warning"]
    assert context.cluster_nodes == ["pve-a", "pve-b", "pve-c", "pve-d"]
    assert len(context.current_running_resources) == 1
    assert context.current_running_resources[0].vmid == 801
    assert context.current_running_resources[0].linked_request_id is None
    assert context.overlapping_approved_requests[0].is_current_request is True
    assert context.overlapping_approved_requests[0].projected_node == "pve-b"
    assert context.overlapping_approved_requests[1].hostname == "approved-overlap"
    assert {item.node for item in context.projected_nodes} == {"pve-a", "pve-b"}


def test_rebuild_reserved_assignments_uses_updated_prior_reservations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(timezone.utc)
    request_a = VMRequest(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000011"),
        reason="A",
        resource_type="lxc",
        hostname="req-a",
        cores=2,
        memory=2048,
        password="encrypted",
        storage="local-lvm",
        environment_type="Test",
        status=VMRequestStatus.approved,
        start_at=now + timedelta(hours=1),
        end_at=now + timedelta(hours=2),
        created_at=now,
        assigned_node="old-a",
    )
    request_b = VMRequest(
        id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000012"),
        reason="B",
        resource_type="lxc",
        hostname="req-b",
        cores=2,
        memory=2048,
        password="encrypted",
        storage="local-lvm",
        environment_type="Test",
        status=VMRequestStatus.approved,
        start_at=now + timedelta(hours=1),
        end_at=now + timedelta(hours=2),
        created_at=now + timedelta(minutes=1),
        assigned_node="old-b",
    )

    seen_reserved_nodes: list[list[str]] = []

    def _fake_select_reserved_target_node(*, db_request, reserved_requests, **kwargs):
        seen_reserved_nodes.append(
            [str(item.assigned_node) for item in reserved_requests]
        )
        node = "new-a" if db_request.hostname == "req-a" else "new-b"
        return SimpleNamespace(
            node=node,
            strategy="priority_dominant_share",
            plan=SimpleNamespace(feasible=True),
        )

    monkeypatch.setattr(
        "app.services.vm_request_placement_service.select_reserved_target_node",
        _fake_select_reserved_target_node,
    )

    selections = vm_request_placement_service.rebuild_reserved_assignments(
        session=None,
        requests=[request_b, request_a],
    )

    assert seen_reserved_nodes == [[], ["new-a"]]
    assert selections[request_a.id].node == "new-a"
    assert selections[request_b.id].node == "new-b"


def test_select_request_placement_falls_back_when_reserved_node_is_unavailable(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        resource_type="lxc",
        password=encrypt_value("strongpass123"),
        start_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        end_at=datetime.now(timezone.utc) + timedelta(hours=1),
        cores=2,
        memory=2048,
        storage="local-lvm",
        hostname="fallback-lxc",
        ostemplate="local:vztmpl/debian-12-standard.tar.zst",
        rootfs_size=8,
        environment_type="Fallback Runtime",
        os_info=None,
        expiry_date=None,
        unprivileged=True,
        assigned_node="pve-a",
        placement_strategy_used="priority_dominant_share",
    )
    placement_request = SimpleNamespace()

    monkeypatch.setattr(
        "app.services.provisioning_service.advisor_service._load_cluster_state",
        lambda: ([], []),
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.advisor_service._build_node_capacities",
        lambda **kwargs: [SimpleNamespace(node="pve-a")],
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.advisor_service._decide_resource_type",
        lambda request: ("lxc", "Prefer LXC for this request."),
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.vm_request_placement_service.build_plan",
        lambda **kwargs: SimpleNamespace(feasible=False),
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.vm_request_repo.get_approved_vm_requests_overlapping_window",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.vm_request_placement_service.select_reserved_target_node",
        lambda **kwargs: SimpleNamespace(
            node="pve-b",
            strategy="priority_dominant_share",
            plan=SimpleNamespace(feasible=True),
        ),
    )

    placement = provisioning_service._select_request_placement(
        session=db,
        db_request=request,
        placement_request=placement_request,
        placement_strategy="priority_dominant_share",
    )

    assert placement.node == "pve-b"
    assert placement.strategy == "priority_dominant_share"
    assert placement.plan.feasible is True


def test_reserved_target_node_prefers_admin_storage_profile(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _create_user(db)
    now = datetime.now(timezone.utc)
    db.add(
        ProxmoxNode(
            name="pve-a",
            host="10.0.0.1",
            port=8006,
            is_primary=True,
            is_online=True,
            priority=5,
        )
    )
    db.add(
        ProxmoxNode(
            name="pve-b",
            host="10.0.0.2",
            port=8006,
            is_primary=False,
            is_online=True,
            priority=5,
        )
    )
    db.add(
        ProxmoxConfig(
            id=1,
            host="pve.local",
            user="root@pam",
            encrypted_password="encrypted",
            verify_ssl=False,
            iso_storage="local",
            data_storage="local-lvm",
            pool_name="CampusCloud",
            placement_strategy="priority_dominant_share",
            cpu_overcommit_ratio=2.0,
            disk_overcommit_ratio=1.0,
        )
    )
    _seed_managed_storage(
        db,
        node_name="pve-a",
        storage="data-hdd",
        speed_tier="hdd",
        user_priority=8,
    )
    _seed_managed_storage(
        db,
        node_name="pve-b",
        storage="data-nvme",
        speed_tier="nvme",
        user_priority=1,
    )
    db.commit()

    request = VMRequest(
        user_id=user.id,
        reason="Need a VM with managed storage placement.",
        resource_type="vm",
        hostname="storage-aware",
        cores=2,
        memory=2048,
        password=encrypt_value("strongpass123"),
        storage="local-lvm",
        environment_type="Storage Aware",
        template_id=100,
        disk_size=40,
        username="student",
        status=VMRequestStatus.approved,
        start_at=now + timedelta(hours=1),
        end_at=now + timedelta(hours=2),
        created_at=now,
    )

    monkeypatch.setattr(
        "app.services.vm_request_placement_service.advisor_service._load_cluster_state",
        lambda: ([], []),
    )
    monkeypatch.setattr(
        "app.services.vm_request_placement_service.advisor_service._build_node_capacities",
        lambda **kwargs: [
            NodeCapacity(
                node="pve-a",
                status="online",
                total_cpu_cores=16,
                allocatable_cpu_cores=16,
                cpu_ratio=0.0,
                total_memory_bytes=64 * 1024**3,
                allocatable_memory_bytes=64 * 1024**3,
                memory_ratio=0.0,
                total_disk_bytes=400 * 1024**3,
                allocatable_disk_bytes=400 * 1024**3,
                disk_ratio=0.0,
                gpu_count=0,
                running_resources=0,
                guest_soft_limit=32,
                guest_pressure_ratio=0.0,
                candidate=True,
            ),
            NodeCapacity(
                node="pve-b",
                status="online",
                total_cpu_cores=16,
                allocatable_cpu_cores=16,
                cpu_ratio=0.0,
                total_memory_bytes=64 * 1024**3,
                allocatable_memory_bytes=64 * 1024**3,
                memory_ratio=0.0,
                total_disk_bytes=400 * 1024**3,
                allocatable_disk_bytes=400 * 1024**3,
                disk_ratio=0.0,
                gpu_count=0,
                running_resources=0,
                guest_soft_limit=32,
                guest_pressure_ratio=0.0,
                candidate=True,
            ),
        ],
    )

    selection = vm_request_placement_service.select_reserved_target_node(
        session=db,
        db_request=request,
        reserved_requests=[],
    )

    assert selection.node == "pve-b"
    assert selection.plan.feasible is True


def test_create_vm_prefers_admin_selected_storage(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _create_user(db)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "app.services.provisioning_service.proxmox_service.next_vmid",
        lambda: 902,
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.proxmox_service.find_vm_template",
        lambda template_id: {"vmid": template_id, "node": "node-d"},
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.vm_request_placement_service.select_best_storage_name",
        lambda **kwargs: "data-nvme",
    )

    def _resolve_target_storage(node, requested_storage, required_content):
        captured["resolved"] = (node, requested_storage, required_content)
        return requested_storage

    monkeypatch.setattr(
        "app.services.provisioning_service.proxmox_service.resolve_target_storage",
        _resolve_target_storage,
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.proxmox_service.clone_vm",
        lambda node, template_id, **clone_config: (
            captured.setdefault("clone", (node, template_id, clone_config)),
            "UPID:clone",
        )[1],
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.proxmox_service.update_config",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.proxmox_service.resize_disk",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.proxmox_service.control",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.firewall_service.setup_default_rules",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.audit_service.log_action",
        lambda *args, **kwargs: None,
    )

    provisioning_service.create_vm(
        session=db,
        user_id=user.id,
        vm_data=VMCreateRequest(
            hostname="admin-storage-choice",
            template_id=779,
            username="student",
            password="strongpass123",
            cores=2,
            memory=2048,
            disk_size=20,
            storage="user-picked-storage",
            environment_type="Managed Storage",
            start=True,
        ),
    )

    assert captured["resolved"] == ("node-d", "data-nvme", "images")
    assert captured["clone"] == (
        "node-d",
        779,
        {
            "newid": 902,
            "name": "admin-storage-choice",
            "full": 1,
            "storage": "data-nvme",
            "pool": "CampusCloud",
        },
    )


def test_process_due_request_starts_rebalances_active_window_and_migrates(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _create_user(db)
    now = datetime.now(timezone.utc)
    existing = VMRequest(
        user_id=user.id,
        reason="Already running request",
        resource_type="vm",
        hostname="active-a",
        cores=2,
        memory=2048,
        password=encrypt_value("strongpass123"),
        storage="local-lvm",
        environment_type="Rebalance Test",
        template_id=101,
        disk_size=20,
        username="student",
        status=VMRequestStatus.approved,
        start_at=now - timedelta(hours=1),
        end_at=now + timedelta(hours=1),
        vmid=701,
        assigned_node="pve-a",
        desired_node="pve-a",
        actual_node="pve-a",
        migration_status=VMMigrationStatus.idle,
        rebalance_epoch=1,
        last_rebalanced_at=now - timedelta(hours=1),
        created_at=now - timedelta(hours=1),
    )
    new_start = VMRequest(
        user_id=user.id,
        reason="New request entering the active slot",
        resource_type="vm",
        hostname="active-b",
        cores=2,
        memory=2048,
        password=encrypt_value("strongpass123"),
        storage="local-lvm",
        environment_type="Rebalance Test",
        template_id=102,
        disk_size=20,
        username="student",
        status=VMRequestStatus.approved,
        start_at=now - timedelta(minutes=1),
        end_at=now + timedelta(hours=1),
        vmid=702,
        assigned_node="pve-b",
        desired_node="pve-b",
        actual_node="pve-b",
        migration_status=VMMigrationStatus.idle,
        rebalance_epoch=0,
        last_rebalanced_at=None,
        created_at=now - timedelta(minutes=5),
    )
    db.add(existing)
    db.add(new_start)
    db.commit()
    db.refresh(existing)
    db.refresh(new_start)

    resources = {
        701: {"vmid": 701, "node": "pve-a", "name": "active-a", "type": "qemu"},
        702: {"vmid": 702, "node": "pve-b", "name": "active-b", "type": "qemu"},
    }
    migrations: list[tuple[str, str, int, str, bool]] = []

    monkeypatch.setattr(
        "app.services.vm_request_schedule_service.engine",
        db.get_bind(),
    )
    monkeypatch.setattr(
        "app.services.vm_request_schedule_service._utc_now",
        lambda: now,
    )
    monkeypatch.setattr(
        "app.services.vm_request_schedule_service.vm_request_placement_service.rebalance_active_assignments",
        lambda **kwargs: {
            existing.id: SimpleNamespace(
                node="pve-c",
                strategy="priority_dominant_share",
                plan=SimpleNamespace(feasible=True),
            ),
            new_start.id: SimpleNamespace(
                node="pve-b",
                strategy="priority_dominant_share",
                plan=SimpleNamespace(feasible=True),
            ),
        },
    )
    monkeypatch.setattr(
        "app.services.vm_request_schedule_service.proxmox_service.find_resource",
        lambda vmid: resources[vmid],
    )
    monkeypatch.setattr(
        "app.services.vm_request_schedule_service.proxmox_service.get_status",
        lambda node, vmid, resource_type: {"status": "running"},
    )
    monkeypatch.setattr(
        "app.services.vm_request_schedule_service.proxmox_service.get_config",
        lambda node, vmid, resource_type: {
            "scsi0": f"local-lvm:vm-{vmid}-disk-0,size=20G",
        },
    )
    monkeypatch.setattr(
        "app.services.vm_request_schedule_service.proxmox_service.list_node_storages",
        lambda node: [{"storage": "local-lvm"}],
    )

    def _migrate(source_node, target_node, vmid, resource_type, online=True, **kwargs):
        migrations.append((source_node, target_node, vmid, resource_type, online))
        resources[vmid]["node"] = target_node
        return "UPID:migrate"

    monkeypatch.setattr(
        "app.services.vm_request_schedule_service.proxmox_service.migrate_resource",
        _migrate,
    )
    monkeypatch.setattr(
        "app.services.vm_request_schedule_service.audit_service.log_action",
        lambda *args, **kwargs: None,
    )

    started_count = vm_request_schedule_service.process_due_request_starts()

    db.expire_all()
    refreshed_existing = db.exec(
        select(VMRequest).where(VMRequest.id == existing.id)
    ).first()
    refreshed_new = db.exec(
        select(VMRequest).where(VMRequest.id == new_start.id)
    ).first()
    assert started_count == 0
    assert migrations == [("pve-a", "pve-c", 701, "qemu", True)]
    assert refreshed_existing is not None
    assert refreshed_existing.assigned_node == "pve-c"
    assert refreshed_existing.desired_node == "pve-c"
    assert refreshed_existing.actual_node == "pve-c"
    assert refreshed_existing.migration_status == VMMigrationStatus.completed
    assert refreshed_existing.rebalance_epoch == 2
    assert refreshed_new is not None
    assert refreshed_new.assigned_node == "pve-b"
    assert refreshed_new.desired_node == "pve-b"
    assert refreshed_new.actual_node == "pve-b"
    assert refreshed_new.rebalance_epoch == 2


def test_process_due_request_starts_provisions_new_active_request_on_rebalanced_node(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _create_user(db)
    now = datetime.now(timezone.utc)
    request = VMRequest(
        user_id=user.id,
        reason="Start and place on the rebalanced node",
        resource_type="lxc",
        hostname="active-new-lxc",
        cores=2,
        memory=2048,
        password=encrypt_value("strongpass123"),
        storage="local-lvm",
        environment_type="Provision Test",
        ostemplate="local:vztmpl/debian-12-standard.tar.zst",
        rootfs_size=8,
        status=VMRequestStatus.approved,
        start_at=now - timedelta(minutes=1),
        end_at=now + timedelta(hours=1),
        created_at=now - timedelta(minutes=2),
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    monkeypatch.setattr(
        "app.services.vm_request_schedule_service.engine",
        db.get_bind(),
    )
    monkeypatch.setattr(
        "app.services.vm_request_schedule_service._utc_now",
        lambda: now,
    )
    monkeypatch.setattr(
        "app.services.vm_request_schedule_service.vm_request_placement_service.rebalance_active_assignments",
        lambda **kwargs: {
            request.id: SimpleNamespace(
                node="pve-b",
                strategy="priority_dominant_share",
                plan=SimpleNamespace(feasible=True),
            )
        },
    )

    def _fake_adopt_or_provision_due_request(**kwargs):
        db_request = kwargs["request"]
        session = kwargs["session"]
        db_request.vmid = 990
        db_request.assigned_node = "pve-b"
        db_request.desired_node = "pve-b"
        db_request.actual_node = "pve-b"
        db_request.placement_strategy_used = "priority_dominant_share"
        session.add(db_request)
        session.flush()
        return 990, "pve-b", "priority_dominant_share", True

    monkeypatch.setattr(
        "app.services.vm_request_schedule_service._adopt_or_provision_due_request",
        _fake_adopt_or_provision_due_request,
    )
    monkeypatch.setattr(
        "app.services.vm_request_schedule_service.proxmox_service.get_config",
        lambda node, vmid, resource_type: {
            "rootfs": f"local-lvm:subvol-{vmid}-disk-0,size=8G",
        },
    )
    monkeypatch.setattr(
        "app.services.vm_request_schedule_service.proxmox_service.list_node_storages",
        lambda node: [{"storage": "local-lvm"}],
    )
    monkeypatch.setattr(
        "app.services.vm_request_schedule_service.audit_service.log_action",
        lambda *args, **kwargs: None,
    )

    started_count = vm_request_schedule_service.process_due_request_starts()

    db.expire_all()
    refreshed = db.exec(select(VMRequest).where(VMRequest.id == request.id)).first()
    assert started_count == 1
    assert refreshed is not None
    assert refreshed.vmid == 990
    assert refreshed.assigned_node == "pve-b"
    assert refreshed.desired_node == "pve-b"
    assert refreshed.actual_node == "pve-b"
    assert refreshed.migration_status == VMMigrationStatus.completed
    assert refreshed.rebalance_epoch == 1
    assert refreshed.last_rebalanced_at == now.replace(tzinfo=None)


def test_migrate_request_to_desired_node_blocks_vm_with_passthrough(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _create_user(db)
    request = VMRequest(
        user_id=user.id,
        reason="Passthrough VM should not auto-migrate",
        resource_type="vm",
        hostname="passthrough-vm",
        cores=2,
        memory=2048,
        password=encrypt_value("strongpass123"),
        storage="local-lvm",
        environment_type="Migration Guard",
        template_id=301,
        disk_size=20,
        username="student",
        status=VMRequestStatus.approved,
        vmid=1201,
        assigned_node="pve-b",
        desired_node="pve-b",
        actual_node="pve-a",
        migration_status=VMMigrationStatus.pending,
        created_at=datetime.now(timezone.utc),
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    monkeypatch.setattr(
        "app.services.vm_request_schedule_service.proxmox_service.get_status",
        lambda node, vmid, resource_type: {"status": "running"},
    )
    monkeypatch.setattr(
        "app.services.vm_request_schedule_service.proxmox_service.get_config",
        lambda node, vmid, resource_type: {
            "hostpci0": "0000:65:00",
            "scsi0": "local-lvm:vm-1201-disk-0,size=20G",
        },
    )
    monkeypatch.setattr(
        "app.services.vm_request_schedule_service.proxmox_service.list_node_storages",
        lambda node: [{"storage": "local-lvm"}],
    )
    monkeypatch.setattr(
        "app.services.vm_request_schedule_service.proxmox_service.migrate_resource",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("migrate_resource should not be called for passthrough VM")
        ),
    )

    result_node = vm_request_schedule_service._migrate_request_to_desired_node(
        session=db,
        request=request,
        current_node="pve-a",
    )

    db.refresh(request)
    assert result_node == "pve-a"
    assert request.actual_node == "pve-a"
    assert request.desired_node == "pve-b"
    assert request.migration_status == VMMigrationStatus.blocked
    assert request.migration_error is not None
    assert "passthrough devices" in request.migration_error


def test_migrate_request_to_desired_node_blocks_lxc_bind_mount(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _create_user(db)
    request = VMRequest(
        user_id=user.id,
        reason="Bind mount container should not auto-migrate",
        resource_type="lxc",
        hostname="bind-lxc",
        cores=2,
        memory=2048,
        password=encrypt_value("strongpass123"),
        storage="local-lvm",
        environment_type="Migration Guard",
        ostemplate="local:vztmpl/debian-12-standard.tar.zst",
        rootfs_size=8,
        status=VMRequestStatus.approved,
        vmid=1301,
        assigned_node="pve-b",
        desired_node="pve-b",
        actual_node="pve-a",
        migration_status=VMMigrationStatus.pending,
        created_at=datetime.now(timezone.utc),
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    monkeypatch.setattr(
        "app.services.vm_request_schedule_service.proxmox_service.get_status",
        lambda node, vmid, resource_type: {"status": "running"},
    )
    monkeypatch.setattr(
        "app.services.vm_request_schedule_service.proxmox_service.get_config",
        lambda node, vmid, resource_type: {
            "rootfs": "local-lvm:subvol-1301-disk-0,size=8G",
            "mp0": "/srv/shared,mp=/data",
        },
    )
    monkeypatch.setattr(
        "app.services.vm_request_schedule_service.proxmox_service.list_node_storages",
        lambda node: [{"storage": "local-lvm"}],
    )
    monkeypatch.setattr(
        "app.services.vm_request_schedule_service.proxmox_service.migrate_resource",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("migrate_resource should not be called for bind-mount LXC")
        ),
    )

    result_node = vm_request_schedule_service._migrate_request_to_desired_node(
        session=db,
        request=request,
        current_node="pve-a",
    )

    db.refresh(request)
    assert result_node == "pve-a"
    assert request.actual_node == "pve-a"
    assert request.desired_node == "pve-b"
    assert request.migration_status == VMMigrationStatus.blocked
    assert request.migration_error is not None
    assert "bind mount" in request.migration_error


def test_spec_change_review_stays_pending_when_apply_fails(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _create_user(db)
    reviewer = _create_user(db, is_superuser=True)
    request = SpecChangeRequest(
        vmid=456,
        user_id=user.id,
        change_type=SpecChangeType.cpu,
        reason="Need more CPU for workload spikes",
        current_cpu=2,
        requested_cpu=4,
        status=SpecChangeRequestStatus.pending,
        created_at=datetime.now(timezone.utc),
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    monkeypatch.setattr(
        "app.services.spec_change_service.proxmox_service.find_resource",
        lambda vmid: {"node": "node-a", "type": "qemu"},
    )
    monkeypatch.setattr(
        "app.services.spec_change_service.proxmox_service.update_config",
        lambda *args, **kwargs: (_ for _ in ()).throw(ProxmoxError("apply failed")),
    )

    with pytest.raises(ProxmoxError):
        spec_change_service.review(
            session=db,
            request_id=request.id,
            review_data=SpecChangeRequestReview(
                status=SpecChangeRequestStatus.approved
            ),
            reviewer=reviewer,
        )

    db.expire_all()
    refreshed = db.exec(
        select(SpecChangeRequest).where(SpecChangeRequest.id == request.id)
    ).first()
    assert refreshed is not None
    assert refreshed.status == SpecChangeRequestStatus.pending
    assert refreshed.applied_at is None
    assert refreshed.reviewer_id is None


def test_create_vm_uses_template_node_and_normalizes_disk_size(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _create_user(db)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "app.services.provisioning_service.proxmox_service.next_vmid",
        lambda: 900,
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.proxmox_service.find_vm_template",
        lambda template_id: {"vmid": template_id, "node": "node-b"},
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.proxmox_service.resolve_target_storage",
        lambda node, requested_storage, required_content: requested_storage,
    )

    def _clone_vm(node, template_id, **clone_config):
        captured["clone"] = (node, template_id, clone_config)
        return "UPID:clone"

    monkeypatch.setattr(
        "app.services.provisioning_service.proxmox_service.clone_vm",
        _clone_vm,
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.proxmox_service.update_config",
        lambda node, vmid, resource_type, **config: captured.setdefault(
            "update", (node, vmid, resource_type, config)
        ),
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.proxmox_service.resize_disk",
        lambda node, vmid, resource_type, disk, size: captured.setdefault(
            "resize", (node, vmid, resource_type, disk, size)
        ),
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.proxmox_service.control",
        lambda node, vmid, resource_type, action: captured.setdefault(
            "control", (node, vmid, resource_type, action)
        ),
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.firewall_service.setup_default_rules",
        lambda node, vmid, resource_type: captured.setdefault(
            "firewall", (node, vmid, resource_type)
        ),
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.audit_service.log_action",
        lambda *args, **kwargs: None,
    )

    result = provisioning_service.create_vm(
        session=db,
        user_id=user.id,
        vm_data=VMCreateRequest(
            hostname="template-node-check",
            template_id=777,
            username="student",
            password="strongpass123",
            cores=4,
            memory=4096,
            disk_size=40,
            storage="fast-ssd",
            environment_type="Node Aware",
            start=True,
        ),
    )

    db.expire_all()
    saved = db.exec(select(Resource).where(Resource.vmid == 900)).first()
    assert saved is not None
    assert captured["clone"] == (
        "node-b",
        777,
        {
            "newid": 900,
            "name": "template-node-check",
            "full": 1,
            "storage": "fast-ssd",
            "pool": "CampusCloud",
        },
    )
    assert captured["resize"] == ("node-b", 900, "qemu", "scsi0", "40G")
    assert captured["control"] == ("node-b", 900, "qemu", "start")
    assert saved.environment_type == "Node Aware"
    assert result.vmid == 900


def test_create_vm_falls_back_when_requested_storage_is_unavailable(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _create_user(db)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "app.services.provisioning_service.proxmox_service.next_vmid",
        lambda: 901,
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.proxmox_service.find_vm_template",
        lambda template_id: {"vmid": template_id, "node": "node-c"},
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.proxmox_service.resolve_target_storage",
        lambda node, requested_storage, required_content: "fast-ssd",
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.proxmox_service.clone_vm",
        lambda node, template_id, **clone_config: (
            captured.setdefault("clone", (node, template_id, clone_config)),
            "UPID:clone",
        )[1],
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.proxmox_service.update_config",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.proxmox_service.resize_disk",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.proxmox_service.control",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.firewall_service.setup_default_rules",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.provisioning_service.audit_service.log_action",
        lambda *args, **kwargs: None,
    )

    provisioning_service.create_vm(
        session=db,
        user_id=user.id,
        vm_data=VMCreateRequest(
            hostname="storage-fallback",
            template_id=778,
            username="student",
            password="strongpass123",
            cores=2,
            memory=2048,
            disk_size=20,
            storage="local-lvm",
            environment_type="Fallback Test",
            start=True,
        ),
    )

    assert captured["clone"] == (
        "node-c",
        778,
        {
            "newid": 901,
            "name": "storage-fallback",
            "full": 1,
            "storage": "fast-ssd",
            "pool": "CampusCloud",
        },
    )


def test_user_role_teacher_is_treated_as_regular_user(db: Session) -> None:
    teacher = _create_user(db, role=UserRole.teacher)

    assert teacher.role == UserRole.teacher
    assert teacher.is_superuser is False
    assert teacher.is_instructor is False


def test_delete_user_rejects_owned_resources(db: Session) -> None:
    owner = _create_user(db)
    admin = _create_user(db, is_superuser=True)
    db.add(
        Resource(
            vmid=999,
            user_id=owner.id,
            environment_type="Owned VM",
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    with pytest.raises(BadRequestError):
        user_service.delete_user(session=db, user_id=owner.id, current_user=admin)

    assert db.get(User, owner.id) is not None


def test_vm_templates_are_filtered_by_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.proxmox_service.get_proxmox_settings",
        lambda: type("Cfg", (), {"pool_name": "CampusCloud"})(),
    )
    monkeypatch.setattr(
        "app.services.proxmox_service._raw_vms",
        lambda: [
            {"vmid": 100, "name": "allowed", "node": "node-a", "template": 1, "pool": "CampusCloud"},
            {"vmid": 101, "name": "blocked", "node": "node-b", "template": 1, "pool": "OtherPool"},
            {"vmid": 102, "name": "not-template", "node": "node-c", "template": 0, "pool": "CampusCloud"},
        ],
    )

    templates = proxmox_service.get_vm_templates()

    assert templates == [
        {"vmid": 100, "name": "allowed", "node": "node-a", "template": 1, "pool": "CampusCloud"}
    ]
