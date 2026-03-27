from datetime import datetime, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.security import encrypt_value
from app.exceptions import BadRequestError, ProxmoxError, ProvisioningError
from app.models import (
    Resource,
    SpecChangeRequest,
    SpecChangeRequestStatus,
    SpecChangeType,
    User,
    UserRole,
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


def test_vm_request_create_preserves_environment_type(db: Session) -> None:
    user = _create_user(db)
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
    )

    result = vm_request_service.create(session=db, request_in=request_in, user=user)

    db.expire_all()
    saved = db.exec(select(VMRequest).where(VMRequest.id == result.id)).first()
    assert saved is not None
    assert result.environment_type == "ML Lab"
    assert saved.environment_type == "ML Lab"
    assert saved.storage == "fast-ssd"


def test_vm_request_review_rolls_back_and_cleans_up_on_failure(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _create_user(db)
    reviewer = _create_user(db, is_superuser=True)
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
        created_at=datetime.now(timezone.utc),
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    cleaned_vmids: list[int] = []

    monkeypatch.setattr(
        "app.services.vm_request_service.provisioning_service.provision_from_request",
        lambda session, db_request: 321,
    )

    def _raise_audit(*args, **kwargs):
        raise RuntimeError("audit failure")

    monkeypatch.setattr(
        "app.services.vm_request_service.audit_service.log_action",
        _raise_audit,
    )
    monkeypatch.setattr(
        "app.services.vm_request_service.provisioning_service.cleanup_provisioned_resource",
        lambda vmid: cleaned_vmids.append(vmid),
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
    assert cleaned_vmids == [321]


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
