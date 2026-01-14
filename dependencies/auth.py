# dependencies/auth.py
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from config import settings
import hashlib
import os

# Для локальной аутентификации
security = HTTPBearer()
ALGORITHM = settings.jwt.algorithm
SECRET_KEY = settings.jwt.secret_key


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
    Хеширование пароля
    """
    salt = os.environ.get("PASSWORD_SALT", "default-salt-change-me")
    return hashlib.sha256((password + salt).encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверка пароля
    """
    return hash_password(plain_password) == hashed_password


async def get_current_user(request: Request):
    """
    Зависимость для получения текущего пользователя из запроса
    Используется в защищенных эндпоинтах
    """
    user_info = getattr(request.state, 'user', None)

    if not user_info or not user_info.get("authenticated"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется аутентификация",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_info


async def require_admin(request: Request):
    """
    Зависимость для проверки прав администратора
    """
    user_info = await get_current_user(request)

    if not user_info.get("is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права администратора"
        )

    return user_info