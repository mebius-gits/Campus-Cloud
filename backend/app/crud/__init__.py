"""
CRUD 模組

此模組包含所有資料庫 CRUD 操作：
- User CRUD 操作
- Item CRUD 操作

所有函數均從此處匯出，保持向後相容性。
"""

from .item import create_item
from .user import (
    DUMMY_HASH,
    authenticate,
    create_user,
    get_user_by_email,
    update_user,
)

__all__ = [
    # User CRUD
    "create_user",
    "update_user",
    "get_user_by_email",
    "authenticate",
    "DUMMY_HASH",
    # Item CRUD
    "create_item",
]
