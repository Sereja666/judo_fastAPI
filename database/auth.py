import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import jwt
from config import settings

# Импортируем модель Telegram_user из ваших моделей
from database.models import Telegram_user

SECRET_KEY = settings.SECRET  # Используйте свой секретный ключ
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
    query = select(Telegram_user).where(
        Telegram_user.phone == phone,
        Telegram_user.is_active == True
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Создание JWT токена"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


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