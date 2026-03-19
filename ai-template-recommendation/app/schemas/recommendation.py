from __future__ import annotations

from pydantic import BaseModel, Field


class DeviceNode(BaseModel):
    node: str
    maxcpu: int = Field(default=0)
    cpu_usage_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    maxmem_gb: float = Field(default=0.0, ge=0.0)
    mem_usage_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    gpu_count: int = Field(default=0, ge=0)


class RecommendationRequest(BaseModel):
    goal: str = Field(..., min_length=3)
    role: str = Field(default="student")
    course_context: str = Field(default="coursework")
    sharing_scope: str = Field(default="personal")
    budget_mode: str = Field(default="balanced")
    preferred_type: str | None = Field(default=None)
    expected_users: int = Field(default=1, ge=1, le=100000)
    requires_gpu: bool = False
    needs_windows: bool = False
    needs_public_web: bool = False
    needs_persistent_storage: bool = True
    needs_database: bool = False
    experience_level: str = Field(default="beginner")
    top_k: int = Field(default=5, ge=1, le=10)
    device_nodes: list[DeviceNode] = Field(default_factory=list)

