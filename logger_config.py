import sys
from pathlib import Path
from loguru import logger

# Создаем папку для логов, если она не существует
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Настройка loguru
logger.remove()

# Добавляем обработчик для вывода в консоль
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True
)

# Добавляем обработчик для записи в файл
logger.add(
    logs_dir / "bot.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="INFO",
    rotation="10 MB",
    retention="30 days",
    compression="zip"
)

# Для ошибок добавляем отдельный файл
logger.add(
    logs_dir / "errors.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="ERROR",
    rotation="10 MB",
    retention="30 days",
    compression="zip"
)

# Для отладки можно добавить DEBUG уровень в отдельный файл (по желанию)
logger.add(
    logs_dir / "debug.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
    rotation="10 MB",
    retention="7 days",  # Debug логи храним меньше
    compression="zip"
)

logger.info("✅ Logging system configured successfully")