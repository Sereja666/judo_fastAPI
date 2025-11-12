import redis
from config import settings
import logging

logger = logging.getLogger(__name__)


def get_redis_client() -> redis.Redis:
    """Создание и настройка Redis клиента"""
    try:
        client = redis.Redis(
            host=settings.redis_conf.REDIS_HOST,
            port=settings.redis_conf.REDIS_PORT,
            db=settings.redis_conf.REDIS_DB,
            password=None,  # или ваше значение, если установили пароль
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )

        # Проверяем подключение
        client.ping()
        logger.info(
            f"Redis client initialized successfully: {settings.redis_conf.REDIS_HOST}:{settings.redis_conf.REDIS_PORT}")
        return client

    except Exception as e:
        logger.error(f"Failed to initialize Redis client: {e}")
        raise