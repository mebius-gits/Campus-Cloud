"""資源監控 API：全域 overview、節點/VM RRD 趨勢。"""

from typing import Any

from fastapi import APIRouter, Query

from app.api.deps import AdminUser, CurrentUser, SessionDep
from app.schemas.monitoring import MonitoringOverview
from app.services.monitoring import monitoring_service

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/overview", response_model=MonitoringOverview)
def get_overview(_: AdminUser) -> MonitoringOverview:
    """全域監控匯總（叢集容量/用量、節點與 VM 統計）。"""
    return monitoring_service.get_overview()


@router.get("/nodes/{node}/rrd")
def get_node_rrd(
    node: str,
    _: AdminUser,
    timeframe: str = Query(default="hour"),
) -> list[dict[str, Any]]:
    """節點 RRD 趨勢（直接代理 PVE，timeframe: hour|day|week）。"""
    return monitoring_service.get_node_rrd(node, timeframe)


@router.get("/vms/{vmid}/rrd")
def get_vm_rrd(
    vmid: int,
    session: SessionDep,
    current_user: CurrentUser,
    timeframe: str = Query(default="hour"),
) -> list[dict[str, Any]]:
    """VM/LXC RRD 趨勢（擁有者或管理員）。"""
    return monitoring_service.get_vm_rrd(
        session=session, vmid=vmid, timeframe=timeframe, user=current_user
    )
