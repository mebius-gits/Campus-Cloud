from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ToolCallRecord(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    reply: str
    tools_called: list[ToolCallRecord] = Field(default_factory=list)
    error: str | None = None


class NodeInfo(BaseModel):
    node: str
    status: str
    cpu_usage: float
    cpu_cores: int
    mem_used_bytes: int
    mem_total_bytes: int
    mem_used_pct: float
    disk_used_bytes: int
    disk_total_bytes: int
    disk_used_pct: float
    uptime_seconds: int | None = None


class StorageInfo(BaseModel):
    node: str
    storage: str
    storage_type: str
    content: str
    avail_bytes: int
    used_bytes: int
    total_bytes: int
    used_pct: float
    active: bool
    enabled: bool
    shared: bool


class ResourceSummary(BaseModel):
    vmid: int
    name: str
    resource_type: str
    node: str
    status: str
    pool: str | None = None
    cpu_usage: float
    cpu_cores: int
    mem_used_bytes: int
    mem_total_bytes: int
    mem_used_pct: float
    disk_used_bytes: int
    disk_total_bytes: int
    disk_used_pct: float
    net_in_bytes: int
    net_out_bytes: int
    uptime_seconds: int | None = None
    is_template: bool


class ResourceStatus(BaseModel):
    vmid: int
    node: str
    resource_type: str
    status: str
    cpu_usage: float
    cpu_cores: int
    mem_used_bytes: int
    mem_total_bytes: int
    mem_used_pct: float
    disk_read_bytes: int
    disk_write_bytes: int
    disk_total_bytes: int
    net_in_bytes: int
    net_out_bytes: int
    uptime_seconds: int | None = None
    pid: int | None = None


class ResourceConfig(BaseModel):
    vmid: int
    node: str
    resource_type: str
    name: str | None = None
    cpu_cores: int | None = None
    cpu_type: str | None = None
    memory_mb: int | None = None
    disk_info: str | None = None
    disk_size_gb: int | None = None
    os_type: str | None = None
    net0: str | None = None
    description: str | None = None
    tags: str | None = None
    onboot: bool = False
    protection: bool = False
    raw: dict[str, Any] = Field(default_factory=dict)


class NetworkInterface(BaseModel):
    vmid: int
    name: str
    inet: str | None = None
    inet6: str | None = None
    hwaddr: str | None = None


class ClusterInfo(BaseModel):
    cluster_name: str | None = None
    is_cluster: bool
    node_count: int
    quorate: bool
    cluster_version: int | None = None


class SystemSnapshot(BaseModel):
    collected_at: datetime
    collection_duration_seconds: float
    cluster: ClusterInfo
    nodes: list[NodeInfo]
    storages: list[StorageInfo]
    resources: list[ResourceSummary]
    resource_statuses: list[ResourceStatus]
    resource_configs: list[ResourceConfig]
    network_interfaces: list[NetworkInterface]
    errors: list[str] = Field(default_factory=list)
    total_nodes: int
    online_nodes: int
    total_vms: int
    total_lxc: int
    running_vms: int
    running_lxc: int
