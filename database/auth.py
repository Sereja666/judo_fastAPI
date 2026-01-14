import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from logger_config import logger
import jwt
from config import settings

# Импортируем модель Telegram_user из ваших моделей
from database.models import Telegram_user
from utils.phone_normalizer import normalize_phone

SECRET_KEY = settings.jwt.secret_key  # Используйте свой секретный ключ
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        password_bytes = plain_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_password.encode('utf-8'))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


async def authenticate_user(
        db: AsyncSession,
        phone: str,
        password: str
) -> Optional[Telegram_user]:
    """Аутентификация пользователя по телефону и паролю"""

    logger.info(f"🔑 Попытка аутентификации для телефона: '{phone}'")

    # Нормализуем телефон
    normalized_phone = normalize_phone(phone)
    logger.info(f"🔑 Нормализованный телефон: '{normalized_phone}'")

    if not normalized_phone:
        logger.warning("❌ Не удалось нормализовать телефон")
        return None

    # Пытаемся найти пользователя
    query = select(Telegram_user).where(
        Telegram_user.phone == normalized_phone,
        Telegram_user.is_active == True
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user:
        logger.info(f"✅ Найден пользователь: {user.full_name}")
    else:
        logger.warning(f"❌ Пользователь с телефоном '{normalized_phone}' не найден")

        # Для отладки: покажем похожие телефоны
        from sqlalchemy import or_, like
        similar_query = select(Telegram_user).where(
            Telegram_user.is_active == True
        ).where(
            or_(
                Telegram_user.phone.like(f"%{normalized_phone[-10:]}%"),  # последние 10 цифр
                Telegram_user.phone.like(f"%{normalized_phone[2:]}%")  # без +7
            )
        )
        similar_result = await db.execute(similar_query)
        similar_users = similar_result.scalars().all()

        if similar_users:
            logger.info("📋 Похожие телефоны в базе:")
            for u in similar_users:
                logger.info(f"  • {u.phone} - {u.full_name}")

    if not user:
        return None

    # Проверяем пароль
    password_correct = verify_password(password, user.password_hash)
    logger.info(f"🔑 Проверка пароля: {'✅' if password_correct else '❌'}")

    if not password_correct:
        logger.warning("❌ Неверный пароль")
        return None

    logger.info(f"✅ Успешная аутентификация: {user.full_name}")
    return user


async def get_current_user_from_token(
        db: AsyncSession,
        token: str
) -> Optional[Telegram_user]:
    """Получение пользователя из JWT токена"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        phone: str = payload.get("sub")
        if phone is None:
            return None

        query = select(Telegram_user).where(
            Telegram_user.phone == phone,
            Telegram_user.is_active == True
        )
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        return user

    except jwt.PyJWTError:
        return None