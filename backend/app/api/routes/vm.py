import logging

from fastapi import APIRouter, HTTPException

from app.api.deps import VmInfoDep
from app.core.proxmox import get_proxmox_api
from app.models import VNCInfoSchema

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vm", tags=["vm"])
proxmox = get_proxmox_api()


@router.get("/{vmid}/console", response_model=VNCInfoSchema)
def get_vm_console(vmid: int, vm_info: VmInfoDep):
    try:
        if vm_info["type"] != "qemu":
            raise HTTPException(
                status_code=400, detail=f"Resource {vmid} is not a QEMU VM"
            )

        node = vm_info["node"]
        console_data = proxmox.nodes(node).qemu(vmid).vncproxy.post(websocket=1)
        vnc_ticket = console_data["ticket"]

        ws_url = f"/ws/vnc/{vmid}/"

        logger.info(f"Console URL and ticket generated for VM {vmid}")

        return {
            "vmid": vmid,
            "ws_url": ws_url,
            "ticket": vnc_ticket,
            "message": "Connect to this WebSocket URL to access the VM console",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get console for VM {vmid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
