"""群組相關模型"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel

from .base import get_datetime_utc

if TYPE_CHECKING:
    from .group_member import GroupMember
    from .user import User


class Group(SQLModel, table=True):
    """群組資料庫模型（課程/班級）"""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    owner_id: uuid.UUID = Field(foreign_key="user.id")
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    # Relationships
    owner: Optional["User"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Group.owner_id]"}
    )
    members: list["GroupMember"] = Relationship(back_populates="group")


__all__ = ["Group"]
