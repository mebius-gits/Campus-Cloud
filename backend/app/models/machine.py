"""項目相關模型"""

from __future__ import annotations

from sqlmodel import SQLModel


class NodeSchema(SQLModel):
    """Proxmox node information."""

    node: str
    status: str
    cpu: float | None = None
    maxcpu: int | None = None
    mem: int | None = None
    maxmem: int | None = None
    uptime: int | None = None


class VMSchema(SQLModel):
    """Virtual machine information."""

    vmid: int
    name: str
    status: str
    node: str
    type: str  # "qemu" for VM, "lxc" for container
    cpu: float | None = None
    maxcpu: int | None = None
    mem: int | None = None
    maxmem: int | None = None
    uptime: int | None = None
    netin: int | None = None
    diskread: int | None = None
    diskwrite: int | None = None
    disk: int | None = None
    template: int | None = None
    memhost: int | None = None
    maxdisk: int | None = None


class VNCInfoSchema(SQLModel):
    """VNC console connection information."""

    vmid: int
    ws_url: str
    ticket: str | None = None
    message: str


class TerminalInfoSchema(SQLModel):
    """Terminal console connection information for LXC containers."""

    vmid: int
    ws_url: str
    ticket: str | None = None
    message: str


__all__ = [
    "NodeSchema",
    "VMSchema",
    "VNCInfoSchema",
    "TerminalInfoSchema",
]
