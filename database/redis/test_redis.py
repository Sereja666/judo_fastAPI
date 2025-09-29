# test_redis_connection.py
import redis
import asyncio

from config import settings


async def test_redis_connection():
    try:
        # Пробуем подключиться с настройками по умолчанию
        client = redis.Redis(
            host=settings.redis_conf.REDIS_HOST,
            port=settings.redis_conf.REDIS_PORT,
            db=settings.redis_conf.REDIS_DB,
            password=None,  # или ваше значение, если установили пароль
            decode_responses=True
        )

        # Тестовые операции
        client.set('test_key', 'test_value')
        value = client.get('test_key')
        print(f"✅ Redis подключен успешно! test_key = {value}")

        # Очистка тестовых данных
        client.delete('test_key')

    except Exception as e:
        print(f"❌ Ошибка подключения к Redis: {e}")


if __name__ == "__main__":
    asyncio.run(test_redis_connection())