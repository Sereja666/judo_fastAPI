import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from asyncpg_lite import DatabaseManager
from decouple import config
from config import settings

# Импортируем Redis и middleware
from database.redis.redis_config import get_redis_client
from database.redis.redis_storage import RedisStorage as CustomRedisStorage
from database.middleware import RedisMiddleware, RateLimitMiddleware, LoggingMiddleware

# получаем список администраторов из .env
admins = [int(admin_id) for admin_id in config('ADMINS').split(',')]

# настраиваем логирование и выводим в переменную для отдельного использования в нужных местах
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# инициируем объект, который будет отвечать за взаимодействие с базой данных
db_manager = DatabaseManager(db_url=settings.db.db_url, deletion_password=config('ROOT_PASS'))

# инициируем объект бота, передавая ему parse_mode=ParseMode.HTML по умолчанию
bot = Bot(token=config('TOKEN'), default=DefaultBotProperties(parse_mode=ParseMode.HTML))

# ИНИЦИАЛИЗАЦИЯ STORAGE
redis_storage = None
fsm_storage = None

try:
    redis_client = get_redis_client()

    # Проверяем подключение к Redis
    redis_client.ping()
    logger.info("✅ Redis подключен успешно")

    # Два типа storage:
    # 1. Для FSM состояний Aiogram
    from aiogram.fsm.storage.redis import RedisStorage as FSMRedisStorage

    fsm_storage = FSMRedisStorage(redis=redis_client)

    # 2. Для кастомных данных (выбранные студенты, кэш и т.д.)
    redis_storage = CustomRedisStorage(redis_client)

except Exception as e:
    logger.error(f"❌ Ошибка подключения к Redis: {e}")
    # Fallback на MemoryStorage если Redis недоступен
    from aiogram.fsm.storage.memory import MemoryStorage

    fsm_storage = MemoryStorage()
    logger.info("✅ Используется MemoryStorage как fallback")

# инициируем объект диспетчера с выбранным storage
dp = Dispatcher(storage=fsm_storage)

# ДОБАВЛЯЕМ MIDDLEWARE ТОЛЬКО ЕСЛИ REDIS ДОСТУПЕН
if redis_storage:
    # Middleware для Redis
    redis_middleware = RedisMiddleware(redis_storage)
    dp.update.outer_middleware(redis_middleware)

    # Middleware для rate limiting
    rate_limit_middleware = RateLimitMiddleware(redis_storage)
    dp.message.outer_middleware(rate_limit_middleware)
    logger.info("✅ Redis middleware добавлены")
else:
    logger.info("✅ Redis middleware пропущены (Redis недоступен)")

# Middleware для логирования (всегда добавляем)
logging_middleware = LoggingMiddleware()
dp.update.outer_middleware(logging_middleware)

logger.info("✅ All middleware initialized successfully")


# Функция для получения redis_storage в других модулях
def get_redis_storage():
    return redis_storage


# Функция для проверки доступности Redis
def is_redis_available():
    return redis_storage is not None