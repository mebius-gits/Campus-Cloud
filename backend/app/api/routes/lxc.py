import logging

from fastapi import APIRouter, HTTPException

from app.api.deps import LxcInfoDep
from app.core.proxmox import get_proxmox_api
from app.models import TerminalInfoSchema

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lxc", tags=["lxc"])
proxmox = get_proxmox_api()


@router.get("/{vmid}/terminal", response_model=TerminalInfoSchema)
def get_lxc_terminal(vmid: int, container_info: LxcInfoDep):
    try:
        node = container_info["node"]
        console_data = proxmox.nodes(node).lxc(vmid).termproxy.post()
        terminal_ticket = console_data["ticket"]

        ws_url = f"/ws/terminal/{vmid}/"

        logger.info(f"Terminal URL and ticket generated for LXC {vmid}")

        return {
            "vmid": vmid,
            "ws_url": ws_url,
            "ticket": terminal_ticket,
            "message": "Connect to this WebSocket URL to access the LXC terminal",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get terminal for LXC {vmid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
