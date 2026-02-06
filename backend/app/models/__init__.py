"""
Models 模組

此模組包含所有資料模型定義：
- User 相關模型
- Item 相關模型
- Token 與通用模型

所有模型均從此處匯出，保持向後相容性。
"""

from sqlmodel import SQLModel

from .base import get_datetime_utc
from .item import (
    Item,
    ItemBase,
    ItemCreate,
    ItemPublic,
    ItemsPublic,
    ItemUpdate,
)
from .token import (
    Message,
    NewPassword,
    Token,
    TokenPayload,
)
from .user import (
    UpdatePassword,
    User,
    UserBase,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)

__all__ = [
    # Base
    "SQLModel",
    "get_datetime_utc",
    # User models
    "UserBase",
    "UserCreate",
    "UserRegister",
    "UserUpdate",
    "UserUpdateMe",
    "UpdatePassword",
    "User",
    "UserPublic",
    "UsersPublic",
    # Item models
    "ItemBase",
    "ItemCreate",
    "ItemUpdate",
    "Item",
    "ItemPublic",
    "ItemsPublic",
    # Token & common models
    "Message",
    "Token",
    "TokenPayload",
    "NewPassword",
]
