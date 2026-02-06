"""項目相關模型"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel

from .base import get_datetime_utc

if TYPE_CHECKING:
    from .user import User


# Shared properties
class ItemBase(SQLModel):
    """Item 基礎屬性"""

    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    """建立 Item 時接收的資料"""

    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    """更新 Item 時接收的資料"""

    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    """Item 資料庫模型"""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: "User | None" = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    """API 回傳的 Item 資料"""

    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(SQLModel):
    """API 回傳的 Item 列表"""

    data: list[ItemPublic]
    count: int


__all__ = [
    "ItemBase",
    "ItemCreate",
    "ItemUpdate",
    "Item",
    "ItemPublic",
    "ItemsPublic",
]
