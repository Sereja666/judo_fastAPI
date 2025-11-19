from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from asyncpg_lite import DatabaseManager
from decouple import config
from config import settings

# Импортируем наш настроенный логгер
from logger_config import logger

# Импортируем Redis и middleware
from database.redis.redis_config import get_redis_client
from database.redis.redis_storage import RedisStorage as CustomRedisStorage
from database.middleware import LoggingMiddleware



db_manager = DatabaseManager(db_url=settings.db.db_url, deletion_password=config('ROOT_PASS'))
bot = Bot(token=config('TOKEN'), default=DefaultBotProperties(parse_mode=ParseMode.HTML))

# ИНИЦИАЛИЗАЦИЯ STORAGE
redis_storage = None
fsm_storage = None

logger.info(f"Попытка подключения к Redis: {settings.redis_conf.REDIS_HOST}:{settings.redis_conf.REDIS_PORT}")

try:
    # Получаем Redis клиент
    redis_client = get_redis_client()

    if redis_client is None:
        raise Exception("Redis client is None")

    # Проверяем подключение к Redis
    from aiogram.fsm.storage.redis import RedisStorage as FSMRedisStorage

    fsm_storage = FSMRedisStorage(redis=redis_client)

    # Инициализируем кастомный Redis storage
    redis_storage = CustomRedisStorage(redis_client)
    logger.info("✅ Redis storage инициализирован успешно")

except Exception as e:
    logger.error(f"❌ Ошибка инициализации Redis: {e}")
    # Fallback на MemoryStorage если Redis недоступен
    from aiogram.fsm.storage.memory import MemoryStorage

    fsm_storage = MemoryStorage()
    logger.info("✅ Используется MemoryStorage как fallback")

# инициируем объект диспетчера с выбранным storage
dp = Dispatcher(storage=fsm_storage)

# Middleware для логирования (всегда добавляем)
logging_middleware = LoggingMiddleware()
dp.update.outer_middleware(logging_middleware)

logger.info("✅ Bot initialized successfully")


# Функция для получения redis_storage в других модулях
def get_redis_storage():
    return redis_storage


def is_redis_available():
    return redis_storage is not None