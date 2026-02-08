import logging

from fastapi import APIRouter, HTTPException

from app.api.deps import ResourceInfoDep
from app.core.proxmox import get_proxmox_api
from app.models import NodeSchema, VMSchema

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resources", tags=["resources"])
proxmox = get_proxmox_api()


@router.get("/nodes", response_model=list[NodeSchema])
def list_nodes():
    try:
        nodes = proxmox.nodes.get()
        logger.debug(f"Retrieved {len(nodes)} nodes from Proxmox")
        return nodes
    except Exception as e:
        logger.error(f"Failed to get nodes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=list[VMSchema])
def list_resources(node: str | None = None):
    try:
        result = []
        resources = proxmox.cluster.resources.get(type="vm")

        for resource in resources:
            if node and resource.get("node") != node:
                continue
            result.append(VMSchema(**resource))

        logger.debug(f"Retrieved {len(result)} resources from Proxmox")
        return result
    except Exception as e:
        logger.error(f"Failed to get resources: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{vmid}", response_model=VMSchema)
def get_resource(vmid: int):
    try:
        resources = proxmox.cluster.resources.get(type="vm")
        for resource in resources:
            if resource["vmid"] == vmid:
                return resource

        logger.warning(f"Resource {vmid} not found")
        raise HTTPException(status_code=404, detail=f"Resource {vmid} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get resource {vmid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{vmid}/start")
def start_resource(vmid: int, resource_info: ResourceInfoDep):
    try:
        node = resource_info["node"]
        resource_type = resource_info["type"]

        if resource_type == "qemu":
            proxmox.nodes(node).qemu(vmid).status.start.post()
        else:
            proxmox.nodes(node).lxc(vmid).status.start.post()

        logger.info(f"Resource {vmid} started")
        return {"message": f"Resource {vmid} started"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start resource {vmid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{vmid}/stop")
def stop_resource(vmid: int, resource_info: ResourceInfoDep):
    try:
        node = resource_info["node"]
        resource_type = resource_info["type"]

        if resource_type == "qemu":
            proxmox.nodes(node).qemu(vmid).status.stop.post()
        else:
            proxmox.nodes(node).lxc(vmid).status.stop.post()

        logger.info(f"Resource {vmid} stopped")
        return {"message": f"Resource {vmid} stopped"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop resource {vmid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{vmid}/reboot")
def reboot_resource(vmid: int, resource_info: ResourceInfoDep):
    try:
        node = resource_info["node"]
        resource_type = resource_info["type"]

        if resource_type == "qemu":
            proxmox.nodes(node).qemu(vmid).status.reboot.post()
        else:
            proxmox.nodes(node).lxc(vmid).status.reboot.post()

        logger.info(f"Resource {vmid} rebooted")
        return {"message": f"Resource {vmid} rebooted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reboot resource {vmid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{vmid}/shutdown")
def shutdown_resource(vmid: int, resource_info: ResourceInfoDep):
    try:
        node = resource_info["node"]
        resource_type = resource_info["type"]

        if resource_type == "qemu":
            proxmox.nodes(node).qemu(vmid).status.shutdown.post()
        else:
            proxmox.nodes(node).lxc(vmid).status.shutdown.post()

        logger.info(f"Resource {vmid} shutdown")
        return {"message": f"Resource {vmid} shutdown"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to shutdown resource {vmid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{vmid}/reset")
def reset_resource(vmid: int, resource_info: ResourceInfoDep):
    try:
        node = resource_info["node"]
        resource_type = resource_info["type"]

        if resource_type == "qemu":
            proxmox.nodes(node).qemu(vmid).status.reset.post()
        else:
            proxmox.nodes(node).lxc(vmid).status.reset.post()

        logger.info(f"Resource {vmid} reset")
        return {"message": f"Resource {vmid} reset"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reset resource {vmid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
