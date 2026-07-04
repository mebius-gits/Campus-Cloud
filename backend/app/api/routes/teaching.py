"""教學體驗 API（E2 配置分發 / E3 熱圖 / E6 批次規格），InstructorUser 起跳。"""

import logging

from fastapi import APIRouter, File, Form, UploadFile

from app.api.deps import InstructorUser, SessionDep
from app.schemas import (
    ConfigPushAccepted,
    ConfigPushItemPublic,
    ConfigPushStatusPublic,
)
from app.services.teaching import config_push_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/teaching", tags=["teaching"])


@router.post(
    "/config-push", response_model=ConfigPushAccepted, status_code=202
)
async def start_config_push(
    session: SessionDep,
    current_user: InstructorUser,
    file: UploadFile = File(...),
    target_path: str = Form(...),
    vmids: list[int] = Form(...),
) -> ConfigPushAccepted:
    content = await file.read()
    task_id = config_push_service.start_push(
        session,
        content=content,
        file_name=file.filename or "config",
        target_path=target_path,
        vmids=vmids,
        user=current_user,
    )
    return ConfigPushAccepted(task_id=task_id)


@router.get("/config-push/{task_id}", response_model=ConfigPushStatusPublic)
def get_config_push_status(
    task_id: str, current_user: InstructorUser
) -> ConfigPushStatusPublic:
    task = config_push_service.get_push_status(task_id, current_user)
    return ConfigPushStatusPublic(
        task_id=task.id,
        file_name=task.file_name,
        target_path=task.target_path,
        items=[
            ConfigPushItemPublic(vmid=i.vmid, status=i.status, error=i.error)
            for i in sorted(task.items.values(), key=lambda x: x.vmid)
        ],
    )
