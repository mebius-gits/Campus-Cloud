"""arq worker 進程設定。

啟動方式（docker compose worker 服務）::

    arq app.infrastructure.queue.worker.WorkerSettings

注意：任務模組清單在 ``modules.TASK_MODULES``，@queue_task 裝飾器靠 import
副作用註冊到 registry。
"""

from __future__ import annotations

from typing import Any

from app.infrastructure.queue.arq_client import QUEUE_NAME, get_redis_settings
from app.infrastructure.queue.modules import import_task_modules
from app.infrastructure.queue.registry import registered_functions

import_task_modules()


class WorkerSettings:
    """arq CLI 讀取的設定類別。"""

    functions = registered_functions()
    redis_settings = get_redis_settings()
    queue_name = QUEUE_NAME
    # 克隆/轉範本非冪等，失敗不自動重試
    max_tries = 1
    job_timeout = 3600
    # 併發上限：避免同時打爆 PVE / DB 連線池
    max_jobs = 8
    health_check_interval = 60

    @staticmethod
    async def on_startup(ctx: dict[str, Any]) -> None:  # noqa: ARG004
        pass

    @staticmethod
    async def on_shutdown(ctx: dict[str, Any]) -> None:  # noqa: ARG004
        pass
