"""範本系統的隊列任務註冊。

所有 @queue_task handler 集中在此模組，worker.py 以 import 副作用完成註冊。
實際業務邏輯放在 template_service / clone_service，handler 僅做參數解包與委派。
"""

from __future__ import annotations

import uuid
from typing import Any

from app.infrastructure.queue import queue_task


@queue_task("queue.ping", timeout_seconds=30)
async def ping(
    task_id: uuid.UUID,  # noqa: ARG001 - handler 固定簽名
    payload: dict[str, Any],
) -> dict[str, Any]:
    """隊列健康檢查任務：原樣回傳 payload。"""
    return {"pong": True, "echo": payload}
