import redis
from config import settings

def get_redis_client() -> redis.Redis:
    """Создание и настройка Redis клиента"""
    return redis.Redis(
        host=settings.redis_conf.REDIS_HOST,
        port=settings.redis_conf.REDIS_PORT,
        db=settings.redis_conf.REDIS_DB,
        password=None,  # или ваше значение, если установили пароль
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True
    )
