"""Regression checks for the retired automatic VM migration feature."""

from app.api.main import api_router
from app.schemas.jobs import JobKind
from app.schemas.proxmox_config import ProxmoxConfigPublic, ProxmoxConfigUpdate
from app.services.scheduling import coordinator


def test_migration_routes_are_not_registered() -> None:
    paths = {route.path for route in api_router.routes}
    assert not any(path.startswith("/migration-jobs") for path in paths)


def test_migration_is_not_a_background_job_kind() -> None:
    assert "migration" not in {kind.value for kind in JobKind}


def test_migration_settings_are_not_part_of_public_api() -> None:
    removed = {
        "migration_enabled",
        "migration_max_per_rebalance",
        "migration_min_interval_minutes",
        "migration_retry_limit",
        "migration_worker_concurrency",
        "migration_job_claim_timeout_seconds",
        "migration_retry_backoff_seconds",
        "migration_lxc_live_enabled",
        "rebalance_migration_cost",
        "rebalance_search_max_relocations",
        "rebalance_search_depth",
    }
    assert removed.isdisjoint(ProxmoxConfigPublic.model_fields)
    assert removed.isdisjoint(ProxmoxConfigUpdate.model_fields)


def test_scheduler_has_no_automatic_rebalance_entrypoint() -> None:
    assert not hasattr(coordinator, "_rebalance_active_window")
    assert not hasattr(coordinator, "_process_pending_migration_jobs")
