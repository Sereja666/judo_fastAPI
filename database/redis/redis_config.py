import redis.asyncio as redis
from config import settings
import logging

logger = logging.getLogger(__name__)


def get_redis_client() -> redis.Redis:
    """Создание и настройка асинхронного Redis клиента"""
    try:
        logger.info(
            f"Создание Redis клиента для {settings.redis_conf.REDIS_HOST}:{settings.redis_conf.REDIS_PORT}, db={settings.redis_conf.REDIS_DB}")

        client = redis.Redis(
            host=settings.redis_conf.REDIS_HOST,
            port=settings.redis_conf.REDIS_PORT,
            db=settings.redis_conf.REDIS_DB,
            password=None,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )

        logger.info("✅ Async Redis client created successfully")
        return client

    except Exception as e:
        logger.error(f"❌ Failed to initialize Redis client: {e}")
        return None