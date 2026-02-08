import asyncio
import logging
import ssl
from urllib.parse import quote

import httpx
import websockets
from fastapi import WebSocket, WebSocketDisconnect

from app.api.deps import VmInfoDep
from app.core.config import settings
from app.core.proxmox import get_proxmox_api

logger = logging.getLogger(__name__)


async def vnc_proxy(websocket: WebSocket, vmid: int):
    """WebSocket proxy for VM VNC console access."""
    await websocket.accept()
    logger.info(f"VNC proxy connection request for VM {vmid}")

    pve_websocket = None

    try:
        # Get session ticket using password authentication
        async with httpx.AsyncClient(verify=settings.PROXMOX_VERIFY_SSL) as client:
            auth_response = await client.post(
                f"https://{settings.PROXMOX_HOST}:8006/api2/json/access/ticket",
                data={
                    "username": settings.PROXMOX_USER,
                    "password": settings.PROXMOX_PASSWORD,
                },
            )

            if auth_response.status_code != 200:
                logger.error(
                    f"Proxmox authentication failed: {auth_response.status_code}"
                )
                await websocket.close(code=1008, reason="Authentication failed")
                return

            auth_data = auth_response.json()["data"]
            pve_auth_cookie = auth_data["ticket"]
            logger.info("Retrieved session ticket for VNC WebSocket authentication")

        proxmox = get_proxmox_api()

        # Find VM in cluster resources
        vm_info = None
        for vm in proxmox.cluster.resources.get(type="vm"):
            if vm["vmid"] == vmid:
                vm_info = vm
                break

        if not vm_info:
            logger.error(f"VM {vmid} not found in cluster")
            await websocket.close(code=1008, reason="VM not found")
            return

        node = vm_info["node"]
        logger.info(
            f"VM {vmid} found on node {node}, status: {vm_info.get('status', 'unknown')}"
        )

        # Get VNC proxy ticket
        console_data = proxmox.nodes(node).qemu(vmid).vncproxy.post(websocket=1)
        vnc_port = console_data["port"]
        vnc_ticket = console_data["ticket"]

        encoded_vnc_ticket = quote(vnc_ticket, safe="")
        encoded_auth_cookie = quote(pve_auth_cookie, safe="")

        # WebSocket URL for VNC
        pve_ws_url = (
            f"wss://{settings.PROXMOX_HOST}:8006"
            f"/api2/json/nodes/{node}/qemu/{vmid}/vncwebsocket"
            f"?port={vnc_port}&vncticket={encoded_vnc_ticket}"
        )

        ssl_context = ssl.create_default_context()
        if not settings.PROXMOX_VERIFY_SSL:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        try:
            # Use Cookie with session ticket
            pve_websocket = await websockets.connect(
                pve_ws_url,
                ssl=ssl_context,
                additional_headers={"Cookie": f"PVEAuthCookie={encoded_auth_cookie}"},
            )
            logger.info("Successfully connected to Proxmox VNC WebSocket")
        except websockets.exceptions.InvalidStatus as e:
            logger.error(
                f"Proxmox WebSocket connection rejected: HTTP {e.response.status_code}"
            )
            await websocket.close(code=1008, reason="Proxmox connection failed")
            return

        logger.info(f"WebSocket proxy established for VM {vmid}")

        # Create an event to signal when either connection closes
        disconnect_event = asyncio.Event()

        async def forward_from_proxmox():
            try:
                async for message in pve_websocket:
                    if disconnect_event.is_set():
                        break
                    try:
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        else:
                            await websocket.send_text(message)
                    except Exception as e:
                        logger.debug(f"Error sending to client: {e}")
                        break
            except websockets.exceptions.ConnectionClosed:
                logger.info(f"Proxmox WebSocket closed for VM {vmid}")
            except Exception as e:
                logger.error(f"Error forwarding from Proxmox: {e}")
            finally:
                disconnect_event.set()

        async def forward_to_proxmox():
            try:
                while not disconnect_event.is_set():
                    try:
                        data = await websocket.receive()
                        if "bytes" in data:
                            await pve_websocket.send(data["bytes"])
                        elif "text" in data:
                            await pve_websocket.send(data["text"])
                    except RuntimeError as e:
                        # Handle "Cannot call receive once disconnect message received"
                        if "disconnect" in str(e).lower():
                            logger.info(f"Frontend WebSocket disconnected for VM {vmid}")
                            break
                        raise
            except WebSocketDisconnect:
                logger.info(f"Frontend WebSocket disconnected for VM {vmid}")
            except Exception as e:
                logger.error(f"Error forwarding to Proxmox: {e}")
            finally:
                disconnect_event.set()

        # Run both tasks and wait for either to complete
        forward_from_task = asyncio.create_task(forward_from_proxmox())
        forward_to_task = asyncio.create_task(forward_to_proxmox())

        # Wait for either task to complete, then cancel the other
        _, pending = await asyncio.wait(
            {forward_from_task, forward_to_task}, return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel any pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except Exception as e:
        logger.error(f"Failed to establish WebSocket proxy: {e}", exc_info=True)
        await websocket.close(code=1011, reason=str(e))
    finally:
        if pve_websocket:
            await pve_websocket.close()
        logger.info(f"VNC proxy disconnected for VM {vmid}")
