"""
Redis 連接管理模組

提供全局 Redis 連接池和客戶端管理
"""

import logging

from redis.asyncio import ConnectionPool, Redis

from app.ai_api.config import settings

logger = logging.getLogger(__name__)

# 全局連接池和客戶端
_redis_pool: ConnectionPool | None = None
_redis_client: Redis | None = None


async def init_redis() -> None:
    """
    初始化 Redis 連接池

    在應用啟動時調用
    """
    global _redis_pool, _redis_client

    try:
        _redis_pool = ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,  # 自動解碼為字串
            max_connections=50,  # 最大連接數
            socket_connect_timeout=5,  # 連接超時 5 秒
            socket_keepalive=True,  # 保持連接活躍
        )
        _redis_client = Redis(connection_pool=_redis_pool)

        # 測試連接
        await _redis_client.ping()
        logger.info("Redis connected successfully: %s", settings.redis_url)

    except Exception as e:
        logger.error("Failed to connect to Redis: %s", e)
        raise


async def get_redis() -> Redis:
    """
    獲取 Redis 客戶端

    Returns:
        Redis: 異步 Redis 客戶端實例

    Raises:
        RuntimeError: 如果 Redis 未初始化
    """
    if _redis_client is None:
        logger.warning("Redis not initialized, initializing now...")
        await init_redis()

    if _redis_client is None:
        raise RuntimeError("Redis client is not available")

    return _redis_client


async def close_redis() -> None:
    """
    關閉 Redis 連接

    在應用關閉時調用
    """
    global _redis_client, _redis_pool

    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis client closed")

    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None
        logger.info("Redis connection pool closed")
