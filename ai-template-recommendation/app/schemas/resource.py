from __future__ import annotations

from pydantic import BaseModel


class NodeSchema(BaseModel):
    node: str
    status: str = "online"
    cpu: float | None = None
    maxcpu: int | None = None
    mem: int | None = None
    maxmem: int | None = None
    uptime: int | None = None

