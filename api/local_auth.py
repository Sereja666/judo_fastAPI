# api/local_auth.py
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import timedelta, datetime
from dependencies.auth import create_access_token, verify_password, hash_password
from config import settings

router = APIRouter(prefix="/api/auth/local", tags=["authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: str


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None


# Временная база пользователей
# В реальном приложении нужно хранить в БД
TEMP_USERS_DB = {
    "admin": {
        "username": "admin",
        "email": "admin@1legion.ru",
        "full_name": "Администратор системы",
        "hashed_password": hash_password("admin123"),
        "is_active": True,
        "is_superuser": True,
        "created_at": "2024-01-01T00:00:00"
    },
    "trainer": {
        "username": "trainer",
        "email": "trainer@1legion.ru",
        "full_name": "Тренер Иванов",
        "hashed_password": hash_password("trainer123"),
        "is_active": True,
        "is_superuser": False,
        "created_at": "2024-01-01T00:00:00"
    },
    "user": {
        "username": "user",
        "email": "user@1legion.ru",
        "full_name": "Тестовый пользователь",
        "hashed_password": hash_password("user123"),
        "is_active": True,
        "is_superuser": False,
        "created_at": "2024-01-01T00:00:00"
    }
}


async def authenticate_user(username: str, password: str):
    """Аутентификация пользователя"""
    user = TEMP_USERS_DB.get(username)
    if not user:
        return None

    if not user["is_active"]:
        return None

    if not verify_password(password, user["hashed_password"]):
        return None

    return user


@router.post("/login")
async def login_local(
        response: Response,
        form_data: OAuth2PasswordRequestForm = Depends()
):
    """Локальный вход по логину и паролю"""

    user = await authenticate_user(form_data.username, form_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Создаем JWT токен
    access_token = create_access_token(
        data={
            "sub": user["username"],
            "user_id": user["username"],  # Временно используем username как ID
            "email": user["email"],
            "full_name": user["full_name"],
            "is_superuser": user["is_superuser"]
        }
    )

    # Устанавливаем куку
    response.set_cookie(
        key="local_session",
        value=access_token,
        httponly=True,
        secure=False,  # Для разработки, в продакшене установите True
        max_age=settings.jwt.access_token_expire_minutes * 60,
        samesite="lax",
        path="/"
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user["username"],
        "full_name": user["full_name"],
        "is_superuser": user["is_superuser"]
    }


@router.post("/register")
async def register_local(user_data: RegisterRequest):
    """Регистрация нового пользователя (только для администраторов)"""

    if user_data.username in TEMP_USERS_DB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким логином уже существует"
        )

    # Создаем нового пользователя
    new_user = {
        "username": user_data.username,
        "email": user_data.email,
        "full_name": user_data.full_name,
        "hashed_password": hash_password(user_data.password),
        "is_active": True,
        "is_superuser": False,
        "created_at": datetime.now().isoformat()
    }

    TEMP_USERS_DB[user_data.username] = new_user

    return {
        "message": "Пользователь успешно зарегистрирован",
        "username": user_data.username,
        "email": user_data.email
    }


@router.post("/logout")
async def logout_local(response: Response):
    """Выход из локальной сессии"""
    response.delete_cookie("local_session", path="/")
    return {"message": "Вы успешно вышли из системы"}


@router.get("/me")
async def get_current_user_info(request: Request):
    """Получить информацию о текущем пользователе"""
    from dependencies.auth import verify_token

    # Получаем токен из куки
    token = request.cookies.get("local_session")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется аутентификация"
        )

    # Проверяем токен
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен"
        )

    username = payload.get("sub")
    user = TEMP_USERS_DB.get(username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    # Возвращаем информацию о пользователе (без пароля)
    return {
        "username": user["username"],
        "email": user["email"],
        "full_name": user["full_name"],
        "is_active": user["is_active"],
        "is_superuser": user["is_superuser"],
        "created_at": user.get("created_at")
    }


@router.get("/users")
async def get_users_list():
    """Получить список пользователей (только для теста)"""
    users_list = []
    for username, user_data in TEMP_USERS_DB.items():
        users_list.append({
            "username": user_data["username"],
            "email": user_data["email"],
            "full_name": user_data["full_name"],
            "is_active": user_data["is_active"],
            "is_superuser": user_data["is_superuser"]
        })

    return users_list


@router.get("/test-auth")
async def test_auth():
    """Тестовый эндпоинт для проверки работы API"""
    return {
        "message": "API локальной аутентификации работает",
        "available_users": list(TEMP_USERS_DB.keys())
    }