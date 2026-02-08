import logging
from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.core.proxmox import get_proxmox_api
from app.models import TokenPayload, User

logger = logging.getLogger(__name__)

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


def get_vm_info(vmid: int) -> dict:
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


VmInfoDep = Annotated[dict, Depends(get_vm_info)]


def get_lxc_info(vmid: int) -> dict:
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


LxcInfoDep = Annotated[dict, Depends(get_lxc_info)]


def get_resource_info(vmid: int) -> dict:
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

    return resource_info


ResourceInfoDep = Annotated[dict, Depends(get_resource_info)]
