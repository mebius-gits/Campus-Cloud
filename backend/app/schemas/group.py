"""群組相關 schemas"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ===== Request Schemas =====


class GroupCreate(BaseModel):
    """建立群組"""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class GroupMemberAdd(BaseModel):
    """新增群組成員"""

    emails: list[EmailStr]


# ===== Response Schemas =====


class GroupMemberPublic(BaseModel):
    """群組成員資料"""

    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    added_at: datetime | None = None


class GroupPublic(BaseModel):
    """API 回傳的群組資料"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    owner_id: uuid.UUID
    created_at: datetime | None = None
    member_count: int = 0


class GroupsPublic(BaseModel):
    """群組列表回應"""

    data: list[GroupPublic]
    count: int


class GroupDetailPublic(BaseModel):
    """群組詳情（含成員列表）"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    owner_id: uuid.UUID
    created_at: datetime | None = None
    members: list[GroupMemberPublic] = []


