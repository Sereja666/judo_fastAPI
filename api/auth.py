from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta, datetime
import bcrypt

from database.auth import (
    authenticate_user,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from database.models import get_db_async, Telegram_user
from config import templates
import jwt
from config import settings

router = APIRouter( tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


@router.get("/login-page")
async def login_page(request: Request):
    """Страница входа"""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "superset_url": settings.superset_conf.base_url
    })


@router.post("/login")
async def login_for_access_token(
        request: Request,
        form_data: OAuth2PasswordRequestForm = Depends()
):
    """Получение JWT токена"""
    async with get_db_async() as db:
        # Ищем пользователя по телефону (username в форме - это phone)
        user = await authenticate_user(db, form_data.username, form_data.password)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный телефон или пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Создаем токен
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.phone},
            expires_delta=access_token_expires
        )

        # Обновляем время последнего входа
        user.last_login = datetime.utcnow()
        await db.commit()

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "phone": user.phone,
                "full_name": user.full_name,
                "email": user.email
            }
        }


@router.post("/register")
async def register_user(
        phone: str,
        password: str,
        full_name: str,
        email: str = None,
        telegram_username: str = None
):
    """Регистрация нового пользователя"""
    async with get_db_async() as db:
        # Проверяем, существует ли уже пользователь с таким телефоном
        from sqlalchemy import select
        query = select(Telegram_user).where(Telegram_user.phone == phone)
        result = await db.execute(query)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким телефоном уже существует"
            )

        # Хешируем пароль
        from database.auth import get_password_hash
        hashed_password = get_password_hash(password)

        # Создаем нового пользователя
        new_user = Telegram_user(
            phone=phone,
            password_hash=hashed_password,
            full_name=full_name,
            email=email,
            telegram_username=telegram_username,
            date_reg=datetime.utcnow(),
            is_active=True,
            permissions=0  # Базовые права
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        return {
            "message": "Пользователь успешно зарегистрирован",
            "user_id": new_user.telegram_id
        }


@router.get("/logout")
async def logout_jwt():
    """Выход из системы для JWT авторизации"""
    response = JSONResponse(content={"message": "Вы успешно вышли из системы"})
    # Для JWT достаточно удалить токен на клиенте
    return response


@router.get("/me")
async def get_current_user_info(request: Request):
    """Получение информации о текущем пользователе - ДЕБАГ ВЕРСИЯ"""
    # Проверяем все возможные способы получения пользователя
    user_info = getattr(request.state, 'user', None)

    # Отладочная информация
    import json
    debug_info = {
        "request_state_user": user_info,
        "cookies": dict(request.cookies),
        "headers": {k: v for k, v in request.headers.items() if k.lower() in ['authorization', 'cookie']},
        "url": str(request.url),
        "method": request.method
    }

    print("=" * 80)
    print("🔍 ДЕБАГ /api/auth/me:")
    print(json.dumps(debug_info, indent=2, default=str))
    print("=" * 80)

    if user_info and user_info.get("authenticated"):
        return {
            "authenticated": True,
            "username": user_info.get("username"),
            "user_id": user_info.get("user_id"),
            "phone": user_info.get("phone"),
            "email": user_info.get("email"),
            "auth_type": user_info.get("auth_type", "unknown"),
            "debug": "✅ User from request.state"
        }
    else:
        # Попробуем получить токен напрямую из заголовков/cookie
        auth_header = request.headers.get("Authorization")
        token = None

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            print(f"🔑 Token from Authorization header: {token[:20]}...")
        else:
            token = request.cookies.get("access_token")
            if token:
                print(f"🔑 Token from cookie: {token[:20]}...")

        if token:
            # Пробуем декодировать токен напрямую
            try:
                import jwt
                payload = jwt.decode(token, settings.jwt.secret_key, algorithms=[settings.jwt.algorithm])
                print(f"🔑 Token payload: {payload}")
                return {
                    "authenticated": True,
                    "username": payload.get("sub"),
                    "debug": "✅ User from direct token decode",
                    "token_payload": payload
                }
            except Exception as e:
                print(f"❌ Token decode error: {e}")

        return {
            "authenticated": False,
            "message": "Не авторизован",
            "debug_info": debug_info
        }

@router.get("/choose-login")
async def choose_login_page(request: Request):
    """Страница выбора способа входа"""
    from config import settings

    # Генерируем URL для входа через Superset
    superset_base_url = settings.superset_conf.base_url.rstrip('/')
    callback_url = f"{request.base_url}auth/callback?return_url={request.base_url}"
    superset_login_url = f"{superset_base_url}/login/?next={callback_url}"

    return templates.TemplateResponse("choose_login.html", {
        "request": request,
        "superset_login_url": superset_login_url
    })


@router.get("/login-page")
async def login_page(request: Request):
    """Страница локального входа"""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "superset_url": settings.superset_conf.base_url
    })