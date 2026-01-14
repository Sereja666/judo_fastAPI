# dependencies/auth.py
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from config import settings
import hashlib
import os
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

# Для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Для локальной аутентификации
security = HTTPBearer()
ALGORITHM = settings.jwt.algorithm
SECRET_KEY = settings.jwt.secret_key

# Права доступа
PERMISSION_LEVELS = {
    99: "Разработчик (супер администратор)",
    2: "Администратор",
    1: "Тренер"
}


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Создание JWT токена для локальной аутентификации
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.jwt.access_token_expire_minutes
        )

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    Верификация JWT токена
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Проверяем срок действия
        exp = payload.get("exp")
        if exp is None:
            return None

        if datetime.utcnow() > datetime.fromtimestamp(exp):
            return None

        return payload
    except JWTError:
        return None
    except Exception:
        return None


def hash_password(password: str) -> str:
    """
    Хеширование пароля с использованием bcrypt
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверка пароля с использованием bcrypt
    """
    return pwd_context.verify(plain_password, hashed_password)


async def authenticate_db_user(phone: str, password: str) -> Tuple[bool, Optional[dict], str]:
    """
    Аутентификация пользователя через БД (telegram_user)
    """
    try:
        from database.models import Telegram_user, AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            # Ищем пользователя по номеру телефона
            stmt = select(Telegram_user).where(
                Telegram_user.phone == phone
            )
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return False, None, "Пользователь не найден"

            # Проверяем активность пользователя
            if not getattr(user, 'is_active', True):
                return False, None, "Пользователь деактивирован"

            # Проверяем права доступа (должны быть 99, 2 или 1)
            permissions = getattr(user, 'permissions', 0)
            if permissions not in [99, 2, 1]:
                return False, None, "Недостаточно прав для доступа"

            # Проверяем пароль
            password_hash = getattr(user, 'password_hash', None)
            if not password_hash:
                return False, None, "Пароль не установлен"

            if verify_password(password, password_hash):
                # Обновляем дату последнего входа
                user.last_login = datetime.now()
                await session.commit()

                # Определяем уровень доступа
                is_superuser = permissions == 99
                is_admin = permissions in [99, 2]
                is_trainer = permissions in [99, 2, 1]

                # Формируем информацию о пользователе
                user_info = {
                    "username": phone,  # Используем телефон как username
                    "user_id": user.telegram_id,
                    "telegram_id": user.telegram_id,
                    "telegram_username": user.telegram_username,
                    "full_name": getattr(user, 'full_name', ''),
                    "email": getattr(user, 'email', ''),
                    "phone": phone,
                    "permissions": permissions,
                    "permission_name": PERMISSION_LEVELS.get(permissions, "Неизвестно"),
                    "is_superuser": is_superuser,
                    "is_admin": is_admin,
                    "is_trainer": is_trainer,
                    "is_active": True,
                    "last_login": user.last_login.isoformat() if user.last_login else None,
                    "date_reg": user.date_reg.isoformat() if user.date_reg else None
                }

                return True, user_info, "Успешная аутентификация"

            return False, None, "Неверный пароль"

    except Exception as e:
        print(f"Ошибка аутентификации пользователя: {e}")
        return False, None, f"Ошибка сервера: {str(e)}"


async def create_db_user(user_data: dict) -> Tuple[bool, str, Optional[dict]]:
    """
    Создание нового пользователя в БД (только с правами 99, 2 или 1)
    """
    try:
        from database.models import Telegram_user, AsyncSessionLocal

        # Проверяем права доступа
        permissions = user_data.get('permissions', 1)  # По умолчанию тренер
        if permissions not in [99, 2, 1]:
            return False, "Недопустимый уровень прав. Допустимые значения: 99, 2, 1", None

        async with AsyncSessionLocal() as session:
            # Проверяем, существует ли пользователь с таким номером телефона
            stmt = select(Telegram_user).where(
                Telegram_user.phone == user_data.get('phone')
            )
            result = await session.execute(stmt)
            existing_user = result.scalar_one_or_none()

            if existing_user:
                return False, "Пользователь с таким номером телефона уже существует", None

            # Создаем нового пользователя
            new_user = Telegram_user(
                telegram_id=user_data.get('telegram_id'),
                permissions=permissions,
                telegram_username=user_data.get('telegram_username', ''),
                refer_id=user_data.get('refer_id'),
                date_reg=datetime.now(),
                phone=user_data.get('phone'),
                password_hash=hash_password(user_data.get('password')),
                email=user_data.get('email', ''),
                full_name=user_data.get('full_name', ''),
                last_login=datetime.now(),
                is_active=True
            )

            session.add(new_user)
            await session.commit()

            # Получаем созданного пользователя
            await session.refresh(new_user)

            # Определяем уровень доступа
            is_superuser = permissions == 99
            is_admin = permissions in [99, 2]
            is_trainer = permissions in [99, 2, 1]

            user_info = {
                "username": user_data.get('phone'),
                "user_id": new_user.telegram_id,
                "telegram_id": new_user.telegram_id,
                "telegram_username": new_user.telegram_username,
                "full_name": new_user.full_name,
                "email": new_user.email,
                "phone": new_user.phone,
                "permissions": new_user.permissions,
                "permission_name": PERMISSION_LEVELS.get(new_user.permissions, "Неизвестно"),
                "is_superuser": is_superuser,
                "is_admin": is_admin,
                "is_trainer": is_trainer,
                "is_active": new_user.is_active,
                "last_login": new_user.last_login.isoformat() if new_user.last_login else None,
                "date_reg": new_user.date_reg.isoformat() if new_user.date_reg else None
            }

            return True, "Пользователь успешно создан", user_info

    except Exception as e:
        print(f"Ошибка создания пользователя: {e}")
        return False, f"Ошибка создания пользователя: {str(e)}", None


async def get_user_by_phone(phone: str) -> Tuple[bool, Optional[dict], str]:
    """
    Получение информации о пользователе по номеру телефона
    """
    try:
        from database.models import Telegram_user, AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            stmt = select(Telegram_user).where(
                Telegram_user.phone == phone
            )
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return False, None, "Пользователь не найден"

            # Проверяем права доступа
            permissions = getattr(user, 'permissions', 0)
            if permissions not in [99, 2, 1]:
                return False, None, "Недостаточно прав"

            # Определяем уровень доступа
            is_superuser = permissions == 99
            is_admin = permissions in [99, 2]
            is_trainer = permissions in [99, 2, 1]

            user_info = {
                "username": phone,
                "user_id": user.telegram_id,
                "telegram_id": user.telegram_id,
                "telegram_username": user.telegram_username,
                "full_name": getattr(user, 'full_name', ''),
                "email": getattr(user, 'email', ''),
                "phone": phone,
                "permissions": permissions,
                "permission_name": PERMISSION_LEVELS.get(permissions, "Неизвестно"),
                "is_superuser": is_superuser,
                "is_admin": is_admin,
                "is_trainer": is_trainer,
                "is_active": getattr(user, 'is_active', True),
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "date_reg": user.date_reg.isoformat() if user.date_reg else None
            }

            return True, user_info, "Успешно"

    except Exception as e:
        print(f"Ошибка получения пользователя: {e}")
        return False, None, f"Ошибка сервера: {str(e)}"


async def update_user_password(phone: str, new_password: str) -> Tuple[bool, str]:
    """
    Обновление пароля пользователя
    """
    try:
        from database.models import Telegram_user, AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            stmt = select(Telegram_user).where(
                Telegram_user.phone == phone
            )
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return False, "Пользователь не найден"

            # Обновляем пароль
            user.password_hash = hash_password(new_password)
            await session.commit()

            return True, "Пароль успешно обновлен"

    except Exception as e:
        print(f"Ошибка обновления пароля: {e}")
        return False, f"Ошибка обновления пароля: {str(e)}"


# Зависимости для проверки прав
async def require_superuser(request: Request):
    """Требуются права разработчика (99)"""
    user_info = getattr(request.state, 'user', None)

    if not user_info or not user_info.get("authenticated"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется аутентификация"
        )

    if not user_info.get("is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права разработчика"
        )

    return user_info


async def require_admin(request: Request):
    """Требуются права администратора (99 или 2)"""
    user_info = getattr(request.state, 'user', None)

    if not user_info or not user_info.get("authenticated"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется аутентификация"
        )

    if not user_info.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права администратора"
        )

    return user_info


async def require_trainer(request: Request):
    """Требуются права тренера (99, 2 или 1)"""
    user_info = getattr(request.state, 'user', None)

    if not user_info or not user_info.get("authenticated"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется аутентификация"
        )

    if not user_info.get("is_trainer", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права тренера"
        )

    return user_info