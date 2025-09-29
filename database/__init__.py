from .redis.redis_storage import RedisStorage
from .redis.redis_config import get_redis_client

# Создаем экземпляр для импорта
redis_client = get_redis_client()
redis_storage = RedisStorage(redis_client)

__all__ = ['redis_storage']