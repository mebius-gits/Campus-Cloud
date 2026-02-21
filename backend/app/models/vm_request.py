"""虛擬機申請相關模型"""

import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Column, DateTime, Enum, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .user import User


class VMRequestStatus(str, enum.Enum):
    """虛擬機申請狀態"""
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class VMRequest(SQLModel, table=True):
    """虛擬機申請表，儲存使用者申請虛擬機的資訊與審核狀態."""

    __tablename__ = "vm_requests"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", description="申請者ID")

    # 申請原因
    reason: str = Field(description="申請原因")

    # 資源類型: lxc 或 vm
    resource_type: str = Field(description="資源類型: lxc 或 vm")

    # 共用欄位
    hostname: str = Field(description="主機名稱")
    cores: int = Field(default=2, description="CPU 核心數")
    memory: int = Field(default=2048, description="記憶體 (MB)")
    password: str = Field(description="密碼")
    storage: str = Field(default="local-lvm", description="儲存位置")
    environment_type: str = Field(default="自訂規格", description="環境類型")
    os_info: str | None = Field(default=None, description="作業系統資訊")
    expiry_date: date | None = Field(default=None, description="到期日")

    # LXC 專用
    ostemplate: str | None = Field(default=None, description="LXC 作業系統模板")
    rootfs_size: int | None = Field(default=None, description="LXC 磁碟大小 (GB)")
    unprivileged: bool = Field(default=True, description="LXC 非特權模式")

    # VM 專用
    template_id: int | None = Field(default=None, description="VM 模板 ID")
    disk_size: int | None = Field(default=None, description="VM 磁碟大小 (GB)")
    username: str | None = Field(default=None, description="VM 使用者名稱")

    # 審核狀態
    status: VMRequestStatus = Field(
        default=VMRequestStatus.pending,
        sa_column=Column(Enum(VMRequestStatus), nullable=False, default="pending"),
        description="審核狀態",
    )
    reviewer_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", description="審核者ID"
    )
    review_comment: str | None = Field(default=None, description="審核備註")
    reviewed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="審核時間",
    )

    # 建立後的 VMID（審核通過並建立後填入）
    vmid: int | None = Field(default=None, description="建立後的 VM/Container ID")

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="申請時間",
    )

    # Relationships
    user: Optional["User"] = Relationship(
        back_populates="vm_requests",
        sa_relationship_kwargs={"foreign_keys": "[VMRequest.user_id]"},
    )
    reviewer: Optional["User"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[VMRequest.reviewer_id]"},
    )


# ===== API Schemas =====

class VMRequestCreate(SQLModel):
    """建立虛擬機申請的 Schema."""

    reason: str = Field(min_length=10)
    resource_type: str  # "lxc" 或 "vm"
    hostname: str = Field(pattern=r"^[a-z0-9-]+$")
    cores: int = 2
    memory: int = 2048
    password: str = Field(min_length=8, max_length=128)
    storage: str = "local-lvm"
    os_info: str | None = None
    expiry_date: date | None = None

    # LXC 專用
    ostemplate: str | None = None
    rootfs_size: int | None = None

    # VM 專用
    template_id: int | None = None
    disk_size: int | None = None
    username: str | None = None


class VMRequestReview(SQLModel):
    """審核虛擬機申請的 Schema."""

    status: VMRequestStatus
    review_comment: str | None = None


class VMRequestPublic(SQLModel):
    """公開的虛擬機申請資訊."""

    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str | None = None
    user_full_name: str | None = None
    reason: str
    resource_type: str
    hostname: str
    cores: int
    memory: int
    storage: str
    environment_type: str
    os_info: str | None = None
    expiry_date: date | None = None

    # LXC 專用
    ostemplate: str | None = None
    rootfs_size: int | None = None

    # VM 專用
    template_id: int | None = None
    disk_size: int | None = None
    username: str | None = None

    # 審核狀態
    status: VMRequestStatus
    reviewer_id: uuid.UUID | None = None
    review_comment: str | None = None
    reviewed_at: datetime | None = None
    vmid: int | None = None
    created_at: datetime


class VMRequestsPublic(SQLModel):
    """虛擬機申請列表."""

    data: list[VMRequestPublic]
    count: int


__all__ = [
    "VMRequestStatus",
    "VMRequest",
    "VMRequestCreate",
    "VMRequestReview",
    "VMRequestPublic",
    "VMRequestsPublic",
]
