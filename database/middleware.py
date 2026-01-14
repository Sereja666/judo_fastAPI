from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
import httpx
from urllib.parse import urlencode
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from logger_config import logger
from typing import Optional, Dict, Any

# Импортируем функции для обычной авторизации
from database.auth import get_current_user_from_token
from database.models import get_db_async
import jwt


class DualAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware для двойной авторизации:
    1. Через Superset (старый способ)
    2. Через JWT токен (новый способ)
    """

    def __init__(self, app: ASGIApp, superset_base_url: str):
        super().__init__(app)
        self.public_url = superset_base_url.rstrip('/')
        self.excluded_paths = [
            "/static",
            "/health",
            "/auth/callback",
            "/logout",
            "/choose-login",
            "/local-login",
            "/api/auth/login",  # ✅ API для входа
            "/api/auth/register",  # ✅ API для регистрации
            "/api/auth/me",  # ✅ API для проверки пользователя
            "/debug/"
        ]
        self.check_urls = [
            "http://localhost:8088",
            "http://172.17.0.1:8088"
        ]

    async def dispatch(self, request: Request, call_next):
        # Пропускаем исключенные пути
        if self._should_exclude_path(request.url.path):
            return await call_next(request)

        logger.info(f"🔐 Проверка авторизации для: {request.url.path}")

        # Пробуем оба способа авторизации
        user_info = None

        # 1. Пробуем авторизацию через JWT токен из заголовка
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            user_info = await self._authenticate_jwt(request, token)

        # 2. Пробуем авторизацию через JWT токен из cookie (ВАЖНО!)
        if not user_info:
            jwt_cookie = request.cookies.get("access_token")  # <-- ТАКОЙ ЖЕ КЛЮЧ
            if jwt_cookie:
                user_info = await self._authenticate_jwt(request, jwt_cookie)

        # 3. Если нет JWT, пробуем авторизацию через Superset
        if not user_info:
            session_cookie = request.cookies.get("session")
            if session_cookie:
                user_info = await self._authenticate_superset(session_cookie)

        # 4. Если ни один способ не сработал
        if not user_info:
            logger.warning("❌ Пользователь не авторизован")
            # Перенаправляем на страницу выбора способа входа
            return RedirectResponse(url="/choose-login")

        # Сохраняем информацию о пользователе в state
        request.state.user = user_info
        logger.info(f"✅ Пользователь авторизован: {user_info.get('username', 'Unknown')}")

        return await call_next(request)

    async def _authenticate_jwt(self, request: Request, token: str) -> Optional[Dict[str, Any]]:
        """Аутентификация через JWT токен"""
        try:
            async with get_db_async() as db:
                user = await get_current_user_from_token(db, token)
                if user:
                    return {
                        "authenticated": True,
                        "username": user.full_name or user.phone,
                        "user_id": user.telegram_id,
                        "phone": user.phone,
                        "email": user.email,
                        "auth_type": "jwt"
                    }
        except Exception as e:
            logger.debug(f"🔹 Ошибка JWT аутентификации: {e}")

        return None

    async def _authenticate_superset(self, session_cookie: str) -> Optional[Dict[str, Any]]:
        """Аутентификация через Superset (старый способ)"""
        for base_url in self.check_urls:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{base_url}/api/v1/dashboard/",
                        cookies={"session": session_cookie},
                        timeout=3.0,
                        follow_redirects=True
                    )

                    final_url = str(response.url)
                    logger.debug(f"🔹 {base_url}: final URL = {final_url}, status = {response.status_code}")

                    if '/login/' not in final_url and response.status_code in [200, 403]:
                        # Пытаемся получить имя пользователя
                        username = await self._get_superset_username(session_cookie)
                        return {
                            "authenticated": True,
                            "username": username,
                            "auth_type": "superset"
                        }

                    if '/login/' in final_url:
                        return None

            except Exception as e:
                logger.debug(f"🔹 {base_url}: ошибка - {e}")
                continue

        return None

    async def _get_superset_username(self, session_cookie: str) -> str:
        """Безопасное получение имени пользователя из Superset"""
        for base_url in self.check_urls:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{base_url}/api/v1/me",
                        cookies={"session": session_cookie},
                        timeout=2.0,
                        follow_redirects=False
                    )

                    if response.status_code == 200:
                        user_data = response.json()
                        username = user_data.get('username')
                        if username:
                            logger.debug(f"🔹 Получено имя пользователя: {username}")
                            return username

            except Exception as e:
                logger.debug(f"🔹 Ошибка получения имени пользователя: {e}")
                continue

        return "Пользователь (Superset)"

    def _should_exclude_path(self, path: str) -> bool:
        for excluded in self.excluded_paths:
            if path.startswith(excluded + "/") or path == excluded:
                return True
        return False

    def _create_login_redirect(self, request: Request) -> RedirectResponse:
        """Редирект на страницу выбора входа"""
        return RedirectResponse(url="/choose-login")