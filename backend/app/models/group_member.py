"""群組成員模型"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel

from .base import get_datetime_utc

if TYPE_CHECKING:
    from .group import Group
    from .user import User


class GroupMember(SQLModel, table=True):
    """群組成員關聯表"""

    __tablename__ = "group_member"

    group_id: uuid.UUID = Field(foreign_key="group.id", primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", primary_key=True)
    added_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    # Relationships
    group: Optional["Group"] = Relationship(back_populates="members")
    user: Optional["User"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[GroupMember.user_id]"}
    )


__all__ = ["GroupMember"]
