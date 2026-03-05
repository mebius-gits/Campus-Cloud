import logging
from typing import Annotated

from fastapi import Depends, HTTPException

from app.api.deps.auth import CurrentUser
from app.api.deps.database import SessionDep
from app.core.proxmox import get_proxmox_api
from app.crud import resource as resource_crud

logger = logging.getLogger(__name__)


def _fetch_vm_info(vmid: int) -> dict:
    """Internal helper to fetch VM info from Proxmox (no permission check)."""
    proxmox = get_proxmox_api()
    resources = proxmox.cluster.resources.get(type="vm")

    vm_info = None
    for vm in resources:
        if vm["vmid"] == vmid:
            vm_info = vm
            break

    if not vm_info:
        logger.warning(f"VM {vmid} not found for console request")
        raise HTTPException(status_code=404, detail=f"VM {vmid} not found")

    return vm_info


def _fetch_lxc_info(vmid: int) -> dict:
    """Internal helper to fetch LXC info from Proxmox (no permission check)."""
    proxmox = get_proxmox_api()
    resources = proxmox.cluster.resources.get(type="vm")

    container_info = None
    for resource in resources:
        if resource["vmid"] == vmid and resource["type"] == "lxc":
            container_info = resource
            break

    if not container_info:
        logger.warning(f"LXC container {vmid} not found for terminal request")
        raise HTTPException(status_code=404, detail=f"LXC container {vmid} not found")

    return container_info


def _fetch_resource_info(vmid: int) -> dict:
    """Internal helper to fetch resource info from Proxmox (no permission check)."""
    try:
        proxmox = get_proxmox_api()
        resources = proxmox.cluster.resources.get(type="vm")

        resource_info = None
        for resource in resources:
            if resource["vmid"] == vmid:
                resource_info = resource
                break

        if not resource_info:
            logger.warning(f"Resource {vmid} not found")
            raise HTTPException(status_code=404, detail=f"Resource {vmid} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get resource {vmid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    return resource_info


def check_resource_ownership(
    vmid: int,
    current_user: CurrentUser,
    session: SessionDep,
) -> None:
    """
    Check if the current user owns the resource or is a superuser.
    Raises HTTPException if the user doesn't have permission.
    """
    # Superusers can access all resources
    if current_user.is_superuser:
        return

    # Check if the resource exists in the database
    db_resource = resource_crud.get_resource_by_vmid(session=session, vmid=vmid)

    if not db_resource:
        # Resource not in database - deny access for non-superusers
        logger.warning(
            f"User {current_user.email} attempted to access unregistered resource {vmid}"
        )
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to access this resource",
        )

    # Check if the user owns this resource
    if db_resource.user_id != current_user.id:
        logger.warning(
            f"User {current_user.email} attempted to access resource {vmid} "
            f"owned by user {db_resource.user_id}"
        )
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to access this resource",
        )


def get_vm_info(
    vmid: int,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Get VM info with permission check (requires ownership or admin)."""
    check_resource_ownership(vmid, current_user, session)
    return _fetch_vm_info(vmid)


VmInfoDep = Annotated[dict, Depends(get_vm_info)]


def get_lxc_info(
    vmid: int,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Get LXC info with permission check (requires ownership or admin)."""
    check_resource_ownership(vmid, current_user, session)
    return _fetch_lxc_info(vmid)


LxcInfoDep = Annotated[dict, Depends(get_lxc_info)]


def get_resource_info(
    vmid: int,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Get resource info with permission check (requires ownership or admin)."""
    check_resource_ownership(vmid, current_user, session)
    return _fetch_resource_info(vmid)


ResourceInfoDep = Annotated[dict, Depends(get_resource_info)]
