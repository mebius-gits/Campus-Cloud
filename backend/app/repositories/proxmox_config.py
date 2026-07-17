"""Proxmox 設定資料庫操作"""

from datetime import datetime, timezone

from cryptography.fernet import InvalidToken
from sqlmodel import Session

from app.core.security import decrypt_value, encrypt_value
from app.exceptions import AppError
from app.models.proxmox_config import ProxmoxConfig

_SINGLETON_ID = 1


def get_proxmox_config(session: Session) -> ProxmoxConfig | None:
    return session.get(ProxmoxConfig, _SINGLETON_ID)


def upsert_proxmox_config(
    session: Session,
    host: str,
    user: str,
    password: str | None,
    verify_ssl: bool,
    iso_storage: str,
    data_storage: str,
    api_timeout: int,
    task_check_interval: int,
    pool_name: str,
    ca_cert: str | None = None,  # None=不更新，空字串=清除
    gateway_ip: str = "",
    local_subnet: str | None = None,
    default_node: str | None = None,
    placement_strategy: str = "priority_dominant_share",
    cpu_overcommit_ratio: float = 2.0,
    disk_overcommit_ratio: float = 1.0,
    rebalance_peak_cpu_margin: float = 1.1,
    rebalance_peak_memory_margin: float = 1.05,
    rebalance_loadavg_warn_per_core: float = 0.8,
    rebalance_loadavg_max_per_core: float = 1.5,
    rebalance_loadavg_penalty_weight: float = 0.9,
    rebalance_disk_contention_warn_share: float = 0.7,
    rebalance_disk_contention_high_share: float = 0.9,
    rebalance_disk_penalty_weight: float = 0.75,
    rebalance_cpu_peak_warn_share: float = 0.7,
    rebalance_cpu_peak_high_share: float = 1.2,
    rebalance_memory_peak_warn_share: float = 0.8,
    rebalance_memory_peak_high_share: float = 0.85,
    rebalance_resource_weight_cpu: float = 1.0,
    rebalance_resource_weight_memory: float = 1.0,
    rebalance_resource_weight_disk: float = 1.0,
    scheduled_boot_batch_size: int = 5,
    scheduled_boot_batch_interval_seconds: int = 10,
    scheduled_boot_lead_time_minutes: int = 5,
    window_grace_period_minutes: int = 30,
    practice_session_hours: int = 3,
    practice_warning_minutes: int = 30,
) -> ProxmoxConfig:
    config = session.get(ProxmoxConfig, _SINGLETON_ID)

    if config is None:
        if password is None:
            raise ValueError("初次設定必須提供密碼")
        config = ProxmoxConfig(
            id=_SINGLETON_ID,
            host=host,
            user=user,
            encrypted_password=encrypt_value(password),
            verify_ssl=verify_ssl,
            iso_storage=iso_storage,
            data_storage=data_storage,
            api_timeout=api_timeout,
            task_check_interval=task_check_interval,
            pool_name=pool_name,
            ca_cert=ca_cert if ca_cert else None,
            gateway_ip=gateway_ip or None,
            local_subnet=local_subnet or None,
            default_node=default_node or None,
            placement_strategy=placement_strategy,
            cpu_overcommit_ratio=cpu_overcommit_ratio,
            disk_overcommit_ratio=disk_overcommit_ratio,
            rebalance_peak_cpu_margin=rebalance_peak_cpu_margin,
            rebalance_peak_memory_margin=rebalance_peak_memory_margin,
            rebalance_loadavg_warn_per_core=rebalance_loadavg_warn_per_core,
            rebalance_loadavg_max_per_core=rebalance_loadavg_max_per_core,
            rebalance_loadavg_penalty_weight=rebalance_loadavg_penalty_weight,
            rebalance_disk_contention_warn_share=rebalance_disk_contention_warn_share,
            rebalance_disk_contention_high_share=rebalance_disk_contention_high_share,
            rebalance_disk_penalty_weight=rebalance_disk_penalty_weight,
            rebalance_cpu_peak_warn_share=rebalance_cpu_peak_warn_share,
            rebalance_cpu_peak_high_share=rebalance_cpu_peak_high_share,
            rebalance_memory_peak_warn_share=rebalance_memory_peak_warn_share,
            rebalance_memory_peak_high_share=rebalance_memory_peak_high_share,
            rebalance_resource_weight_cpu=rebalance_resource_weight_cpu,
            rebalance_resource_weight_memory=rebalance_resource_weight_memory,
            rebalance_resource_weight_disk=rebalance_resource_weight_disk,
            scheduled_boot_batch_size=scheduled_boot_batch_size,
            scheduled_boot_batch_interval_seconds=scheduled_boot_batch_interval_seconds,
            scheduled_boot_lead_time_minutes=scheduled_boot_lead_time_minutes,
            window_grace_period_minutes=window_grace_period_minutes,
            practice_session_hours=practice_session_hours,
            practice_warning_minutes=practice_warning_minutes,
        )
        session.add(config)
    else:
        config.host = host
        config.user = user
        if password is not None:
            config.encrypted_password = encrypt_value(password)
        config.verify_ssl = verify_ssl
        config.iso_storage = iso_storage
        config.data_storage = data_storage
        config.api_timeout = api_timeout
        config.task_check_interval = task_check_interval
        config.pool_name = pool_name
        if ca_cert is not None:
            config.ca_cert = ca_cert if ca_cert else None
        config.gateway_ip = gateway_ip or None
        config.local_subnet = local_subnet or None
        config.default_node = default_node or None
        config.placement_strategy = placement_strategy
        config.cpu_overcommit_ratio = cpu_overcommit_ratio
        config.disk_overcommit_ratio = disk_overcommit_ratio
        config.rebalance_peak_cpu_margin = rebalance_peak_cpu_margin
        config.rebalance_peak_memory_margin = rebalance_peak_memory_margin
        config.rebalance_loadavg_warn_per_core = rebalance_loadavg_warn_per_core
        config.rebalance_loadavg_max_per_core = rebalance_loadavg_max_per_core
        config.rebalance_loadavg_penalty_weight = rebalance_loadavg_penalty_weight
        config.rebalance_disk_contention_warn_share = rebalance_disk_contention_warn_share
        config.rebalance_disk_contention_high_share = rebalance_disk_contention_high_share
        config.rebalance_disk_penalty_weight = rebalance_disk_penalty_weight
        config.rebalance_cpu_peak_warn_share = rebalance_cpu_peak_warn_share
        config.rebalance_cpu_peak_high_share = rebalance_cpu_peak_high_share
        config.rebalance_memory_peak_warn_share = rebalance_memory_peak_warn_share
        config.rebalance_memory_peak_high_share = rebalance_memory_peak_high_share
        config.rebalance_resource_weight_cpu = rebalance_resource_weight_cpu
        config.rebalance_resource_weight_memory = rebalance_resource_weight_memory
        config.rebalance_resource_weight_disk = rebalance_resource_weight_disk
        config.scheduled_boot_batch_size = scheduled_boot_batch_size
        config.scheduled_boot_batch_interval_seconds = scheduled_boot_batch_interval_seconds
        config.scheduled_boot_lead_time_minutes = scheduled_boot_lead_time_minutes
        config.window_grace_period_minutes = window_grace_period_minutes
        config.practice_session_hours = practice_session_hours
        config.practice_warning_minutes = practice_warning_minutes
        config.updated_at = datetime.now(timezone.utc)
        session.add(config)

    session.commit()
    session.refresh(config)
    return config


def get_decrypted_password(config: ProxmoxConfig) -> str:
    try:
        return decrypt_value(config.encrypted_password)
    except InvalidToken as e:
        raise AppError(
            "無法解密儲存的 Proxmox 密碼：加密金鑰已變更，請重新儲存 Proxmox 設定",
            status_code=400,
        ) from e


__all__ = [
    "get_proxmox_config",
    "upsert_proxmox_config",
    "get_decrypted_password",
]
