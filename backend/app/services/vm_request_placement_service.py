from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import uuid

from sqlmodel import Session

from app.ai.pve_advisor import recommendation_service as advisor_service
from app.ai.pve_advisor.schemas import (
    NodeCapacity,
    PlacementDecision,
    PlacementPlan,
    PlacementRequest,
    ResourceType,
)
from app.models import VMRequest
from app.repositories import proxmox_config as proxmox_config_repo
from app.repositories import proxmox_node as proxmox_node_repo
from app.repositories import proxmox_storage as proxmox_storage_repo
from app.repositories import vm_request as vm_request_repo

GIB = 1024**3
_STORAGE_SPEED_RANK = {"nvme": 0, "ssd": 1, "hdd": 2, "unknown": 3}


@dataclass
class CurrentPlacementSelection:
    node: str | None
    strategy: str
    plan: PlacementPlan


@dataclass
class _WorkingStoragePool:
    storage: str
    total_gb: float
    avail_gb: float
    active: bool
    enabled: bool
    can_vm: bool
    can_lxc: bool
    is_shared: bool
    speed_tier: str
    user_priority: int
    placed_count: int = 0
    overcommit_placed_count: int = 0


@dataclass
class _StorageSelection:
    pool: _WorkingStoragePool
    projected_share: float
    speed_rank: int
    user_priority: int


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _request_window(db_request: VMRequest) -> tuple[datetime | None, datetime | None]:
    return _normalize_datetime(db_request.start_at), _normalize_datetime(db_request.end_at)


def _request_capacity_tuple(db_request: VMRequest) -> tuple[float, int, int]:
    cpu_cores = float(db_request.cores or 1)
    memory_bytes = int(db_request.memory or 512) * 1024 * 1024
    disk_gb = (
        int(db_request.disk_size or 0)
        if db_request.resource_type == "vm"
        else int(db_request.rootfs_size or 0)
    )
    if disk_gb <= 0:
        disk_gb = 20 if db_request.resource_type == "vm" else 8
    return cpu_cores, memory_bytes, disk_gb * GIB


def _build_storage_pool_state(
    *,
    session: Session,
    node_names: list[str],
) -> tuple[dict[str, list[_WorkingStoragePool]], bool]:
    storages = proxmox_storage_repo.get_all_storages(session)
    if not storages:
        return {node_name: [] for node_name in node_names}, False

    shared_registry: dict[str, _WorkingStoragePool] = {}
    by_node: dict[str, list[_WorkingStoragePool]] = {node_name: [] for node_name in node_names}
    node_set = set(node_names)

    for storage in storages:
        node_name = str(storage.node_name or "")
        if node_name not in node_set:
            continue

        if storage.is_shared:
            pool = shared_registry.get(storage.storage)
            if pool is None:
                pool = _WorkingStoragePool(
                    storage=storage.storage,
                    total_gb=float(storage.total_gb or 0.0),
                    avail_gb=float(storage.avail_gb or 0.0),
                    active=bool(storage.active),
                    enabled=bool(storage.enabled),
                    can_vm=bool(storage.can_vm),
                    can_lxc=bool(storage.can_lxc),
                    is_shared=bool(storage.is_shared),
                    speed_tier=str(storage.speed_tier or "unknown"),
                    user_priority=int(storage.user_priority or 5),
                )
                shared_registry[storage.storage] = pool
            by_node[node_name].append(pool)
            continue

        by_node[node_name].append(
            _WorkingStoragePool(
                storage=storage.storage,
                total_gb=float(storage.total_gb or 0.0),
                avail_gb=float(storage.avail_gb or 0.0),
                active=bool(storage.active),
                enabled=bool(storage.enabled),
                can_vm=bool(storage.can_vm),
                can_lxc=bool(storage.can_lxc),
                is_shared=bool(storage.is_shared),
                speed_tier=str(storage.speed_tier or "unknown"),
                user_priority=int(storage.user_priority or 5),
            )
        )

    has_managed_storage = any(pools for pools in by_node.values())
    return by_node, has_managed_storage


def _select_best_storage_for_request(
    *,
    storage_pools: list[_WorkingStoragePool],
    resource_type: ResourceType,
    disk_gb: int,
    disk_overcommit_ratio: float,
) -> _StorageSelection | None:
    if disk_gb <= 0:
        return None

    capable = [
        pool
        for pool in storage_pools
        if pool.active
        and pool.enabled
        and ((resource_type == "lxc" and pool.can_lxc) or (resource_type == "vm" and pool.can_vm))
    ]
    if not capable:
        return None

    normal = [pool for pool in capable if pool.avail_gb + 1e-9 >= float(disk_gb)]
    if normal:
        chosen = min(
            normal,
            key=lambda pool: (
                _STORAGE_SPEED_RANK.get(pool.speed_tier, 3),
                int(pool.user_priority or 5),
                pool.placed_count,
                -float(pool.avail_gb),
                pool.storage,
            ),
        )
        return _StorageSelection(
            pool=chosen,
            projected_share=_projected_share(
                used=max(chosen.total_gb - chosen.avail_gb, 0.0) + float(disk_gb),
                total=max(chosen.total_gb, 1.0),
            ),
            speed_rank=_STORAGE_SPEED_RANK.get(chosen.speed_tier, 3),
            user_priority=int(chosen.user_priority or 5),
        )

    overcommit = [
        pool
        for pool in capable
        if (max(float(pool.total_gb) * max(disk_overcommit_ratio, 1.0) - (pool.total_gb - pool.avail_gb), 0.0) + 1e-9)
        >= float(disk_gb)
    ]
    if not overcommit:
        return None

    chosen = min(
        overcommit,
        key=lambda pool: (
            pool.overcommit_placed_count,
            _STORAGE_SPEED_RANK.get(pool.speed_tier, 3),
            int(pool.user_priority or 5),
            -max(
                float(pool.total_gb) * max(disk_overcommit_ratio, 1.0) - (pool.total_gb - pool.avail_gb),
                0.0,
            ),
            pool.storage,
        ),
    )
    effective_total = max(float(chosen.total_gb) * max(disk_overcommit_ratio, 1.0), 1.0)
    current_used = max(chosen.total_gb - chosen.avail_gb, 0.0)
    return _StorageSelection(
        pool=chosen,
        projected_share=_projected_share(
            used=current_used + float(disk_gb),
            total=effective_total,
        ),
        speed_rank=_STORAGE_SPEED_RANK.get(chosen.speed_tier, 3),
        user_priority=int(chosen.user_priority or 5),
    )


def _reserve_storage_pool(
    *,
    selection: _StorageSelection,
    disk_gb: int,
    disk_overcommit_ratio: float,
) -> None:
    pool = selection.pool
    remaining_physical = max(float(pool.avail_gb), 0.0)
    requested = float(max(disk_gb, 0))
    if remaining_physical + 1e-9 >= requested:
        pool.avail_gb = max(remaining_physical - requested, 0.0)
        pool.placed_count += 1
        return

    current_used = max(pool.total_gb - remaining_physical, 0.0)
    effective_total = max(float(pool.total_gb) * max(disk_overcommit_ratio, 1.0), float(pool.total_gb))
    remaining_effective = max(effective_total - current_used, 0.0)
    if remaining_effective + 1e-9 >= requested:
        pool.avail_gb = max(remaining_physical - requested, 0.0)
        pool.overcommit_placed_count += 1
        return

    raise ValueError(f"Storage pool {pool.storage} does not have enough capacity")


def _refresh_node_candidate(node: NodeCapacity) -> None:
    node.guest_pressure_ratio = advisor_service._guest_pressure_ratio(
        int(node.running_resources),
        int(node.total_cpu_cores),
    )
    node.guest_overloaded = (
        node.guest_pressure_ratio >= advisor_service.settings.guest_pressure_threshold
    )
    node.candidate = (
        node.status == "online"
        and node.allocatable_cpu_cores > 0
        and node.allocatable_memory_bytes > 0
        and node.allocatable_disk_bytes > 0
        and not node.guest_overloaded
    )


def _release_request_from_capacities(
    *,
    node_capacities: list[NodeCapacity],
    db_request: VMRequest,
    node_name: str | None,
) -> None:
    if not node_name:
        return
    node = next((item for item in node_capacities if item.node == node_name), None)
    if node is None:
        return

    cpu_cores, memory_bytes, disk_bytes = _request_capacity_tuple(db_request)
    node.allocatable_cpu_cores = min(
        round(node.allocatable_cpu_cores + cpu_cores, 2),
        round(float(node.total_cpu_cores), 2),
    )
    node.allocatable_memory_bytes = min(
        node.allocatable_memory_bytes + memory_bytes,
        int(node.total_memory_bytes),
    )
    node.allocatable_disk_bytes = min(
        node.allocatable_disk_bytes + disk_bytes,
        int(node.total_disk_bytes),
    )
    node.running_resources = max(int(node.running_resources) - 1, 0)
    _refresh_node_candidate(node)


def _reserve_request_on_capacities(
    *,
    node_capacities: list[NodeCapacity],
    db_request: VMRequest,
    node_name: str,
) -> None:
    node = next((item for item in node_capacities if item.node == node_name), None)
    if node is None:
        raise ValueError(f"Target node {node_name} not found in capacity list")

    cpu_cores, memory_bytes, disk_bytes = _request_capacity_tuple(db_request)
    node.allocatable_cpu_cores = max(
        round(node.allocatable_cpu_cores - cpu_cores, 2),
        0.0,
    )
    node.allocatable_memory_bytes = max(node.allocatable_memory_bytes - memory_bytes, 0)
    node.allocatable_disk_bytes = max(node.allocatable_disk_bytes - disk_bytes, 0)
    node.running_resources = int(node.running_resources) + 1
    _refresh_node_candidate(node)


def _hour_window_iter(start_at: datetime, end_at: datetime) -> list[datetime]:
    if end_at <= start_at:
        return [start_at]
    cursor = start_at.replace(minute=0, second=0, microsecond=0)
    if cursor < start_at:
        cursor += timedelta(hours=1)
    checkpoints: list[datetime] = []
    while cursor < end_at:
        checkpoints.append(cursor)
        cursor += timedelta(hours=1)
    return checkpoints or [start_at]


def _apply_reserved_requests_to_capacities(
    *,
    baseline_capacities,
    reserved_requests: list[VMRequest],
    at_time: datetime,
):
    adjusted = [item.model_copy(deep=True) for item in baseline_capacities]
    by_node = {item.node: item for item in adjusted}

    for reserved in reserved_requests:
        reserved_start = _normalize_datetime(reserved.start_at)
        reserved_end = _normalize_datetime(reserved.end_at)
        assigned_node = str(reserved.assigned_node or "")
        if not reserved_start or not reserved_end or not assigned_node:
            continue
        if not (reserved_start <= at_time < reserved_end):
            continue

        node = by_node.get(assigned_node)
        if not node:
            continue

        reserved_cpu, reserved_memory, reserved_disk = _request_capacity_tuple(reserved)
        node.allocatable_cpu_cores = max(node.allocatable_cpu_cores - reserved_cpu, 0.0)
        node.allocatable_memory_bytes = max(node.allocatable_memory_bytes - reserved_memory, 0)
        node.allocatable_disk_bytes = max(node.allocatable_disk_bytes - reserved_disk, 0)
        node.candidate = (
            node.status == "online"
            and node.allocatable_cpu_cores > 0
            and node.allocatable_memory_bytes > 0
            and node.allocatable_disk_bytes > 0
        )

    return adjusted


def build_plan(
    *,
    session: Session,
    request: PlacementRequest,
    node_capacities: list[NodeCapacity],
    effective_resource_type: ResourceType,
    resource_type_reason: str,
    placement_strategy: str | None = None,
    node_priorities: dict[str, int] | None = None,
) -> PlacementPlan:
    strategy = _normalize_strategy(placement_strategy or get_placement_strategy(session))
    priorities = node_priorities or get_node_priorities(session)
    working_nodes = [item.model_copy(deep=True) for item in node_capacities]
    storage_pools_by_node, has_managed_storage = _build_storage_pool_state(
        session=session,
        node_names=[item.node for item in working_nodes],
    )
    _, disk_overcommit_ratio = get_overcommit_ratios(session)
    required_cpu = advisor_service._effective_cpu_cores(request, effective_resource_type)
    required_memory = advisor_service._effective_memory_bytes(request, effective_resource_type)
    required_disk = request.disk_gb * GIB
    placements: dict[str, int] = {item.node: 0 for item in working_nodes}
    remaining = request.instance_count

    while remaining > 0:
        candidates: list[tuple[NodeCapacity, _StorageSelection | None]] = []
        for item in working_nodes:
            if not item.candidate or not advisor_service._can_fit(
                item,
                cores=required_cpu,
                memory_bytes=required_memory,
                disk_bytes=required_disk,
                gpu_required=request.gpu_required,
            ):
                continue

            storage_selection: _StorageSelection | None = None
            if has_managed_storage:
                storage_selection = _select_best_storage_for_request(
                    storage_pools=storage_pools_by_node.get(item.node, []),
                    resource_type=str(request.resource_type),
                    disk_gb=int(request.disk_gb),
                    disk_overcommit_ratio=disk_overcommit_ratio,
                )
                if storage_selection is None:
                    continue

            candidates.append((item, storage_selection))
        if not candidates:
            break

        chosen, chosen_storage = min(
            candidates,
            key=lambda candidate: _placement_sort_key(
                candidate[0],
                placements=placements,
                priorities=priorities,
                strategy=strategy,
                cores=required_cpu,
                memory_bytes=required_memory,
                disk_bytes=required_disk,
                storage_selection=candidate[1],
            ),
        )
        placements[chosen.node] += 1
        chosen.allocatable_cpu_cores = max(
            chosen.allocatable_cpu_cores - required_cpu,
            0.0,
        )
        chosen.allocatable_memory_bytes = max(
            chosen.allocatable_memory_bytes - required_memory,
            0,
        )
        chosen.allocatable_disk_bytes = max(
            chosen.allocatable_disk_bytes - required_disk,
            0,
        )
        chosen.running_resources += 1
        chosen.guest_pressure_ratio = advisor_service._guest_pressure_ratio(
            chosen.running_resources,
            int(chosen.total_cpu_cores),
        )
        chosen.guest_overloaded = (
            chosen.guest_pressure_ratio
            >= advisor_service.settings.guest_pressure_threshold
        )
        chosen.candidate = (
            chosen.status == "online"
            and chosen.allocatable_cpu_cores > 0
            and chosen.allocatable_memory_bytes > 0
            and chosen.allocatable_disk_bytes > 0
            and not chosen.guest_overloaded
        )
        if chosen_storage is not None:
            _reserve_storage_pool(
                selection=chosen_storage,
                disk_gb=int(request.disk_gb),
                disk_overcommit_ratio=disk_overcommit_ratio,
            )
        remaining -= 1

    assigned = request.instance_count - remaining
    placement_decisions = [
        PlacementDecision(
            node=item.node,
            instance_count=placements[item.node],
            cpu_cores_reserved=round(placements[item.node] * required_cpu, 2),
            memory_bytes_reserved=placements[item.node] * required_memory,
            disk_bytes_reserved=placements[item.node] * required_disk,
            remaining_cpu_cores=round(item.allocatable_cpu_cores, 2),
            remaining_memory_bytes=item.allocatable_memory_bytes,
            remaining_disk_bytes=item.allocatable_disk_bytes,
        )
        for item in working_nodes
        if placements[item.node] > 0
    ]
    placement_decisions.sort(key=lambda item: (-item.instance_count, item.node))

    return PlacementPlan(
        feasible=remaining == 0,
        requested_resource_type=request.resource_type,
        effective_resource_type=effective_resource_type,
        resource_type_reason=resource_type_reason,
        assigned_instances=assigned,
        unassigned_instances=remaining,
        recommended_node=placement_decisions[0].node if placement_decisions else None,
        summary=advisor_service._build_summary_text(
            request=request,
            placement_decisions=placement_decisions,
            effective_resource_type=effective_resource_type,
            assigned=assigned,
            remaining=remaining,
        ),
        rationale=advisor_service._build_rationale(
            request=request,
            placement_decisions=placement_decisions,
            effective_resource_type=effective_resource_type,
            node_capacities=node_capacities,
        ),
        warnings=advisor_service._build_warnings(
            node_capacities=node_capacities,
            request=request,
            effective_resource_type=effective_resource_type,
            remaining=remaining,
        ),
        placements=placement_decisions,
        candidate_nodes=node_capacities,
    )


def select_current_target_node(
    *,
    session: Session,
    db_request: VMRequest,
) -> CurrentPlacementSelection:
    request = _to_placement_request(db_request)
    nodes, resources = advisor_service._load_cluster_state()
    cpu_overcommit_ratio, disk_overcommit_ratio = get_overcommit_ratios(session)
    node_capacities = advisor_service._build_node_capacities(
        nodes=nodes,
        resources=resources,
        cpu_overcommit_ratio=cpu_overcommit_ratio,
        disk_overcommit_ratio=disk_overcommit_ratio,
    )
    effective_resource_type, resource_type_reason = advisor_service._decide_resource_type(
        request
    )
    plan = build_plan(
        session=session,
        request=request,
        node_capacities=node_capacities,
        effective_resource_type=effective_resource_type,
        resource_type_reason=resource_type_reason,
    )
    return CurrentPlacementSelection(
        node=plan.recommended_node,
        strategy=get_placement_strategy(session),
        plan=plan,
    )


def select_reserved_target_node(
    *,
    session: Session,
    db_request: VMRequest,
    reserved_requests: list[VMRequest] | None = None,
) -> CurrentPlacementSelection:
    start_at, end_at = _request_window(db_request)
    return select_reserved_target_node_for_request(
        session=session,
        request=_to_placement_request(db_request),
        start_at=start_at,
        end_at=end_at,
        reserved_requests=reserved_requests,
    )


def select_reserved_target_node_for_request(
    *,
    session: Session,
    request: PlacementRequest,
    start_at: datetime | None,
    end_at: datetime | None,
    reserved_requests: list[VMRequest] | None = None,
) -> CurrentPlacementSelection:
    if not start_at or not end_at:
        nodes, resources = advisor_service._load_cluster_state()
        cpu_overcommit_ratio, disk_overcommit_ratio = get_overcommit_ratios(session)
        node_capacities = advisor_service._build_node_capacities(
            nodes=nodes,
            resources=resources,
            cpu_overcommit_ratio=cpu_overcommit_ratio,
            disk_overcommit_ratio=disk_overcommit_ratio,
        )
        effective_resource_type, resource_type_reason = (
            advisor_service._decide_resource_type(request)
        )
        plan = build_plan(
            session=session,
            request=request,
            node_capacities=node_capacities,
            effective_resource_type=effective_resource_type,
            resource_type_reason=resource_type_reason,
        )
        return CurrentPlacementSelection(
            node=plan.recommended_node,
            strategy=get_placement_strategy(session),
            plan=plan,
        )

    nodes, resources = advisor_service._load_cluster_state()
    cpu_overcommit_ratio, disk_overcommit_ratio = get_overcommit_ratios(session)
    baseline_capacities = advisor_service._build_node_capacities(
        nodes=nodes,
        resources=resources,
        cpu_overcommit_ratio=cpu_overcommit_ratio,
        disk_overcommit_ratio=disk_overcommit_ratio,
    )
    effective_resource_type, resource_type_reason = advisor_service._decide_resource_type(
        request
    )
    if reserved_requests is None:
        reserved_requests = vm_request_repo.get_approved_vm_requests_overlapping_window(
            session=session,
            window_start=start_at,
            window_end=end_at,
        )
    checkpoints = [start_at] + [
        checkpoint
        for checkpoint in _hour_window_iter(start_at, end_at)
        if checkpoint != start_at
    ]

    feasible_nodes = {item.node for item in baseline_capacities}
    start_capacities = baseline_capacities

    for index, checkpoint in enumerate(checkpoints):
        adjusted_capacities = _apply_reserved_requests_to_capacities(
            baseline_capacities=baseline_capacities,
            reserved_requests=reserved_requests,
            at_time=checkpoint,
        )
        if index == 0:
            start_capacities = adjusted_capacities

        hour_feasible_nodes = {
            item.node
            for item in adjusted_capacities
            if advisor_service._can_fit(
                item,
                cores=advisor_service._effective_cpu_cores(
                    request, effective_resource_type
                ),
                memory_bytes=advisor_service._effective_memory_bytes(
                    request, effective_resource_type
                ),
                disk_bytes=request.disk_gb * GIB,
                gpu_required=request.gpu_required,
            )
        }
        feasible_nodes &= hour_feasible_nodes
        if not feasible_nodes:
            break

    strategy = get_placement_strategy(session)
    if not feasible_nodes:
        return CurrentPlacementSelection(
            node=None,
            strategy=strategy,
            plan=build_plan(
                session=session,
                request=request,
                node_capacities=[],
                effective_resource_type=effective_resource_type,
                resource_type_reason=resource_type_reason,
                placement_strategy=strategy,
                node_priorities=get_node_priorities(session),
            ),
        )

    filtered_start_capacities = [
        item for item in start_capacities if item.node in feasible_nodes
    ]
    plan = build_plan(
        session=session,
        request=request,
        node_capacities=filtered_start_capacities,
        effective_resource_type=effective_resource_type,
        resource_type_reason=resource_type_reason,
        placement_strategy=strategy,
        node_priorities=get_node_priorities(session),
    )
    return CurrentPlacementSelection(
        node=plan.recommended_node,
        strategy=strategy,
        plan=plan,
    )


def rebuild_reserved_assignments(
    *,
    session: Session,
    requests: list[VMRequest],
) -> dict[uuid.UUID, CurrentPlacementSelection]:
    """Rebuild node reservations for all approved requests in chronological order."""
    ordered_requests = sorted(
        requests,
        key=lambda item: (
            _normalize_datetime(item.start_at) or datetime.min.replace(tzinfo=UTC),
            _normalize_datetime(item.reviewed_at) or datetime.min.replace(tzinfo=UTC),
            _normalize_datetime(item.created_at) or datetime.min.replace(tzinfo=UTC),
            str(item.id),
        ),
    )
    reserved_so_far: list[VMRequest] = []
    selections: dict[uuid.UUID, CurrentPlacementSelection] = {}

    for request in ordered_requests:
        selection = select_reserved_target_node(
            session=session,
            db_request=request,
            reserved_requests=reserved_so_far,
        )
        if not selection.node or not selection.plan.feasible:
            raise ValueError(
                f"No feasible reservation exists for request {request.id}"
            )
        request.assigned_node = selection.node
        request.placement_strategy_used = selection.strategy
        selections[request.id] = selection
        reserved_so_far.append(request)

    return selections


def rebalance_active_assignments(
    *,
    session: Session,
    requests: list[VMRequest],
) -> dict[uuid.UUID, CurrentPlacementSelection]:
    ordered_requests = sorted(
        requests,
        key=lambda item: (
            _normalize_datetime(item.start_at) or datetime.min.replace(tzinfo=UTC),
            _normalize_datetime(item.reviewed_at) or datetime.min.replace(tzinfo=UTC),
            _normalize_datetime(item.created_at) or datetime.min.replace(tzinfo=UTC),
            str(item.id),
        ),
    )
    nodes, resources = advisor_service._load_cluster_state()
    cpu_overcommit_ratio, disk_overcommit_ratio = get_overcommit_ratios(session)
    working_nodes = advisor_service._build_node_capacities(
        nodes=nodes,
        resources=resources,
        cpu_overcommit_ratio=cpu_overcommit_ratio,
        disk_overcommit_ratio=disk_overcommit_ratio,
    )
    strategy = get_placement_strategy(session)
    priorities = get_node_priorities(session)

    for request in ordered_requests:
        if request.vmid is not None:
            _release_request_from_capacities(
                node_capacities=working_nodes,
                db_request=request,
                node_name=str(request.actual_node or request.assigned_node or ""),
            )

    selections: dict[uuid.UUID, CurrentPlacementSelection] = {}
    for request in ordered_requests:
        placement_request = _to_placement_request(request)
        effective_resource_type, resource_type_reason = advisor_service._decide_resource_type(
            placement_request
        )
        plan = build_plan(
            session=session,
            request=placement_request,
            node_capacities=working_nodes,
            effective_resource_type=effective_resource_type,
            resource_type_reason=resource_type_reason,
            placement_strategy=strategy,
            node_priorities=priorities,
        )
        if not plan.feasible or not plan.recommended_node:
            raise ValueError(f"No feasible active rebalance exists for request {request.id}")
        _reserve_request_on_capacities(
            node_capacities=working_nodes,
            db_request=request,
            node_name=plan.recommended_node,
        )
        selections[request.id] = CurrentPlacementSelection(
            node=plan.recommended_node,
            strategy=strategy,
            plan=plan,
        )

    return selections


def get_placement_strategy(session: Session) -> str:
    config = proxmox_config_repo.get_proxmox_config(session)
    if not config:
        return "priority_dominant_share"
    return _normalize_strategy(config.placement_strategy)


def get_overcommit_ratios(session: Session) -> tuple[float, float]:
    config = proxmox_config_repo.get_proxmox_config(session)
    if not config:
        return 1.0, 1.0

    return (
        max(float(config.cpu_overcommit_ratio or 1.0), 1.0),
        max(float(config.disk_overcommit_ratio or 1.0), 1.0),
    )


def get_node_priorities(session: Session) -> dict[str, int]:
    return {item.name: int(item.priority) for item in proxmox_node_repo.get_all_nodes(session)}


def select_best_storage_name(
    *,
    session: Session,
    node_name: str,
    resource_type: str,
    disk_gb: int,
    fallback_storage: str | None = None,
) -> str | None:
    storage_pools_by_node, has_managed_storage = _build_storage_pool_state(
        session=session,
        node_names=[node_name],
    )
    if not has_managed_storage:
        return fallback_storage

    _, disk_overcommit_ratio = get_overcommit_ratios(session)
    selection = _select_best_storage_for_request(
        storage_pools=storage_pools_by_node.get(node_name, []),
        resource_type=resource_type,
        disk_gb=disk_gb,
        disk_overcommit_ratio=disk_overcommit_ratio,
    )
    if selection is None:
        return None
    return selection.pool.storage


def _placement_sort_key(
    node: NodeCapacity,
    *,
    placements: dict[str, int],
    priorities: dict[str, int],
    strategy: str,
    cores: float,
    memory_bytes: int,
    disk_bytes: int,
    storage_selection: _StorageSelection | None = None,
) -> tuple:
    projected_cpu_share = _projected_share(
        used=max(node.total_cpu_cores - node.allocatable_cpu_cores, 0.0) + cores,
        total=max(node.total_cpu_cores, 1.0),
    )
    projected_memory_share = _projected_share(
        used=max(node.total_memory_bytes - node.allocatable_memory_bytes, 0) + memory_bytes,
        total=max(node.total_memory_bytes, 1),
    )
    projected_disk_share = _projected_share(
        used=max(node.total_disk_bytes - node.allocatable_disk_bytes, 0) + disk_bytes,
        total=max(node.total_disk_bytes, 1),
    )
    dominant_share = max(projected_cpu_share, projected_memory_share, projected_disk_share)
    average_share = (
        projected_cpu_share + projected_memory_share + projected_disk_share
    ) / 3.0
    placement_count = placements.get(node.node, 0)
    storage_speed_rank = (
        storage_selection.speed_rank if storage_selection is not None else 99
    )
    storage_user_priority = (
        storage_selection.user_priority if storage_selection is not None else 99
    )
    storage_projected_share = (
        storage_selection.projected_share if storage_selection is not None else 1.0
    )

    return (
        priorities.get(node.node, 5),
        placement_count,
        dominant_share,
        average_share,
        projected_cpu_share,
        storage_speed_rank,
        storage_user_priority,
        storage_projected_share,
        node.node,
    )


def _normalize_strategy(strategy: str | None) -> str:
    # The scheduler now always respects node priority first.
    # When priorities are equal, placement_count + dominant share keep distribution fair.
    return "priority_dominant_share"


def _projected_share(*, used: float | int, total: float | int) -> float:
    denominator = float(total or 1.0)
    return float(used) / denominator if denominator > 0 else 1.0


def _to_placement_request(db_request: VMRequest) -> PlacementRequest:
    disk_gb = (
        int(db_request.disk_size or 0)
        if db_request.resource_type == "vm"
        else int(db_request.rootfs_size or 0)
    )
    if disk_gb <= 0:
        disk_gb = 20 if db_request.resource_type == "vm" else 8

    return PlacementRequest(
        resource_type=db_request.resource_type,
        cpu_cores=int(db_request.cores or 1),
        memory_mb=int(db_request.memory or 512),
        disk_gb=disk_gb,
        instance_count=1,
        gpu_required=0,
    )
