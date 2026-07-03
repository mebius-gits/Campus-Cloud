"""監控與治理 API schemas。"""

from pydantic import BaseModel


class NodeMetrics(BaseModel):
    """單一節點即時用量（來源：PVE /nodes）。"""

    node: str
    status: str
    cpu: float
    maxcpu: int
    mem: int
    maxmem: int
    disk: int
    maxdisk: int
    uptime: int


class VMTopEntry(BaseModel):
    """高耗用 VM/LXC 條目（來源：PVE cluster/resources）。"""

    vmid: int
    name: str
    node: str
    type: str
    cpu: float
    mem: int
    maxmem: int
    status: str


class MonitoringOverview(BaseModel):
    """全域監控匯總。"""

    nodes_online: int
    nodes_total: int
    cpu_used: float
    cpu_total: int
    mem_used: int
    mem_total: int
    disk_used: int
    disk_total: int
    vms_running: int
    vms_stopped: int
    lxc_running: int
    lxc_stopped: int
    nodes: list[NodeMetrics]
    top_cpu: list[VMTopEntry]
    top_mem: list[VMTopEntry]
