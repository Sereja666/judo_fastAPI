# api/local_auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, validator
import re
from datetime import timedelta
from dependencies.auth import (
    create_access_token,
    authenticate_db_user,
    create_db_user,
    get_user_by_phone,
    update_user_password,
    PERMISSION_LEVELS
)
from config import settings
from typing import Optional

router = APIRouter(prefix="/api/auth/local", tags=["authentication"])


class LoginRequest(BaseModel):
    phone: str
    password: str

    @validator('phone')
    def validate_phone(cls, v):
        # Очищаем номер телефона от лишних символов
        phone = re.sub(r'\D', '', v)
        if len(phone) not in [10, 11]:
            raise ValueError('Номер телефона должен содержать 10-11 цифр')
        return phone


class RegisterRequest(BaseModel):
    phone: str
    email: Optional[EmailStr] = None
    password: str
    full_name: str
    telegram_username: Optional[str] = None
    telegram_id: Optional[int] = None
    permissions: int = 1  # По умолчанию тренер

    @validator('phone')
    def validate_phone(cls, v):
        phone = re.sub(r'\D', '', v)
        if len(phone) not in [10, 11]:
            raise ValueError('Номер телефона должен содержать 10-11 цифр')
        return phone

    @validator('permissions')
    def validate_permissions(cls, v):
        if v not in [99, 2, 1]:
            raise ValueError('Недопустимые права. Допустимые значения: 99, 2, 1')
        return v

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Пароль должен содержать минимум 6 символов')
        return v


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    telegram_username: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Пароль должен содержать минимум 6 символов')
        return v


class UserResponse(BaseModel):
    username: str
    phone: str
    email: Optional[str]
    full_name: Optional[str]
    telegram_username: Optional[str]
    telegram_id: Optional[int]
    permissions: int
    permission_name: str
    is_superuser: bool
    is_admin: bool
    is_trainer: bool
    is_active: bool
    last_login: Optional[str] = None
    date_reg: Optional[str] = None


@router.post("/login")
async def login_local(
        response: Response,
        form_data: OAuth2PasswordRequestForm = Depends()
):
    """Локальный вход по номеру телефона и паролю"""

    # Используем username как номер телефона
    phone = form_data.username

    # Очищаем номер телефона
    phone = re.sub(r'\D', '', phone)

    auth_result, user_info, message = await authenticate_db_user(phone, form_data.password)

    if not auth_result or not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message,
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Создаем JWT токен
    access_token = create_access_token(
        data={
            "sub": user_info["phone"],  # Используем телефон как идентификатор
            "user_id": user_info.get("user_id"),
            "telegram_id": user_info.get("telegram_id"),
            "telegram_username": user_info.get("telegram_username"),
            "full_name": user_info.get("full_name", ""),
            "email": user_info.get("email", ""),
            "phone": user_info["phone"],
            "permissions": user_info.get("permissions", 1),
            "is_superuser": user_info.get("is_superuser", False),
            "is_admin": user_info.get("is_admin", False),
            "is_trainer": user_info.get("is_trainer", True)
        }
    )

    # Устанавливаем куку
    response.set_cookie(
        key="local_session",
        value=access_token,
        httponly=True,
        secure=True if "api.srm-1legion.ru" in settings.superset_conf.base_url else False,
        max_age=settings.jwt.access_token_expire_minutes * 60,
        samesite="lax",
        path="/"
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_info,
        "message": "Успешный вход"
    }


@router.post("/register")
async def register_local(user_data: RegisterRequest):
    """Регистрация нового пользователя (только для администраторов)"""

    success, message, user_info = await create_db_user({
        'phone': user_data.phone,
        'email': user_data.email,
        'full_name': user_data.full_name,
        'password': user_data.password,
        'telegram_username': user_data.telegram_username,
        'telegram_id': user_data.telegram_id,
        'permissions': user_data.permissions
    })

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    return {
        "message": message,
        "user": user_info
    }


@router.post("/logout")
async def logout_local(response: Response):
    """Выход из локальной сессии"""
    response.delete_cookie("local_session", path="/")
    return {"message": "Вы успешно вышли из системы"}


@router.get("/me", response_model=UserResponse)
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

    phone = payload.get("sub")

    # Получаем пользователя из БД
    success, user_info, message = await get_user_by_phone(phone)

    if not success:
        # Если не нашли в БД, возвращаем информацию из токена
        return UserResponse(
            username=phone,
            phone=phone,
            email=payload.get("email"),
            full_name=payload.get("full_name"),
            telegram_username=payload.get("telegram_username"),
            telegram_id=payload.get("telegram_id"),
            permissions=payload.get("permissions", 1),
            permission_name=PERMISSION_LEVELS.get(payload.get("permissions", 1), "Неизвестно"),
            is_superuser=payload.get("is_superuser", False),
            is_admin=payload.get("is_admin", False),
            is_trainer=payload.get("is_trainer", True),
            is_active=True,
            last_login=None,
            date_reg=None
        )

    return UserResponse(**user_info)


@router.post("/change-password")
async def change_password(
        request: Request,
        password_data: PasswordChange
):
    """Смена пароля текущего пользователя"""
    from dependencies.auth import verify_token, authenticate_db_user

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

    phone = payload.get("sub")

    # Проверяем текущий пароль
    auth_result, _, message = await authenticate_db_user(phone, password_data.current_password)
    if not auth_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный текущий пароль"
        )

    # Обновляем пароль
    success, message = await update_user_password(phone, password_data.new_password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    return {"message": "Пароль успешно изменен"}


@router.get("/check-phone/{phone}")
async def check_phone_availability(phone: str):
    """Проверка доступности номера телефона"""
    try:
        from database.models import Telegram_user, AsyncSessionLocal
        from sqlalchemy.future import select

        # Очищаем номер телефона
        phone_clean = re.sub(r'\D', '', phone)

        async with AsyncSessionLocal() as session:
            # Проверяем, существует ли пользователь с таким номером телефона
            stmt = select(Telegram_user).where(
                Telegram_user.phone == phone_clean
            )
            result = await session.execute(stmt)
            existing_user = result.scalar_one_or_none()

            available = existing_user is None

            return {
                "phone": phone_clean,
                "available": available,
                "message": "Номер телефона доступен" if available else "Номер телефона уже зарегистрирован"
            }
    except Exception as e:
        print(f"Ошибка проверки номера телефона: {e}")
        return {
            "phone": phone,
            "available": False,
            "message": "Ошибка при проверке номера телефона"
        }


@router.get("/permission-levels")
async def get_permission_levels():
    """Получить список доступных уровней прав"""
    return {
        "permission_levels": PERMISSION_LEVELS,
        "allowed_for_auth": [99, 2, 1],
        "description": "Только пользователи с правами 99 (Разработчик), 2 (Администратор) или 1 (Тренер) могут войти в систему"
    }


@router.get("/health")
async def auth_health():
    """Проверка работоспособности модуля аутентификации"""
    return {
        "status": "healthy",
        "auth_type": "local_jwt",
        "storage": "telegram_user table",
        "login_field": "phone",
        "password_field": "password_hash",
        "required_permissions": [99, 2, 1],
        "hash_algorithm": "bcrypt"
    }