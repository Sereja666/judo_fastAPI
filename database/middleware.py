# database/middleware.py - ПОЛНОСТЬЮ ПЕРЕПИСАННЫЙ
from fastapi import Request
from fastapi.responses import RedirectResponse
import httpx
from urllib.parse import urlencode
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from logger_config import logger
from dependencies.auth import verify_token


class SafeSupersetAuthMiddleware(BaseHTTPMiddleware):
    """
    Умный middleware для двойной аутентификации:
    1. Superset сессия (кука "session")
    2. Локальная JWT аутентификация (кука "local_session" или Authorization header)
    """

    def __init__(self, app: ASGIApp, superset_base_url: str):
        super().__init__(app)
        self.superset_url = superset_base_url.rstrip('/')

        # Публичные пути (не требуют аутентификации)
        self.public_paths = [
            "/static",
            "/health",
            "/login",
            "/auth/callback",
            "/logout",
            "/api/auth/local/login",
            "/api/auth/local/register",
            "/api/auth/local/test-auth",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico",
            "/debug/"
        ]

        # URL для проверки Superset (с учетом вашей структуры)
        self.check_urls = [
            "http://localhost:8088",
            "http://172.17.0.1:8088",
            self.superset_url
        ]

    async def dispatch(self, request: Request, call_next):
        # Проверяем, является ли путь публичным
        if self._is_public_path(request.url.path):
            return await call_next(request)

        logger.debug(f"🔐 Проверка аутентификации для пути: {request.url.path}")

        # Пытаемся получить пользователя любым способом
        user_info = await self._get_authenticated_user(request)

        if user_info:
            # Добавляем информацию о пользователе в request state
            request.state.user = user_info
            logger.info(f"✅ Аутентифицирован: {user_info.get('username')} ({user_info.get('auth_method')})")
            return await call_next(request)

        # Если пользователь не аутентифицирован - редирект на страницу входа
        logger.warning(f"❌ Неаутентифицированный доступ к {request.url.path}")
        return RedirectResponse(url="/login")

    async def _get_authenticated_user(self, request: Request):
        """Проверяет все доступные методы аутентификации"""

        # 1. Проверяем локальную JWT аутентификацию
        local_user = await self._get_local_user(request)
        if local_user:
            return local_user

        # 2. Проверяем Superset аутентификацию
        superset_user = await self._get_superset_user(request)
        if superset_user:
            return superset_user

        return None

    async def _get_local_user(self, request: Request):
        """Проверка локальной JWT аутентификации"""
        token = None

        # Проверяем Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

        # Проверяем сессионную куку
        if not token:
            token = request.cookies.get("local_session")

        if not token:
            return None

        # Проверяем JWT токен
        payload = verify_token(token)
        if payload:
            logger.debug(f"🔐 Найден локальный JWT токен для пользователя: {payload.get('sub')}")
            return {
                "authenticated": True,
                "auth_method": "local",
                "username": payload.get("sub"),
                "user_id": payload.get("user_id"),
                "email": payload.get("email"),
                "full_name": payload.get("full_name"),
                "is_superuser": payload.get("is_superuser", False),
                "token_payload": payload
            }

        return None

    async def _get_superset_user(self, request: Request):
        """Проверка Superset аутентификации"""
        session_cookie = request.cookies.get("session")

        if not session_cookie:
            return None

        # Проверяем аутентификацию в Superset
        is_authenticated = await self._check_superset_auth(session_cookie)

        if is_authenticated:
            username = await self._get_superset_username(session_cookie)
            logger.debug(f"🔐 Найдена Superset сессия для пользователя: {username}")
            return {
                "authenticated": True,
                "auth_method": "superset",
                "username": username,
                "email": f"{username}@superset.local",  # Заглушка
                "full_name": username,
                "is_superuser": False  # Superset пользователи не админы в локальной системе
            }

        return None

    async def _check_superset_auth(self, session_cookie: str) -> bool:
        """Проверка валидности Superset сессии"""
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
                    logger.debug(f"🔹 Superset check {base_url}: {final_url}, status {response.status_code}")

                    # Если не редирект на логин и статус 200/403 - сессия валидна
                    if '/login/' not in final_url and response.status_code in [200, 403]:
                        return True

                    if '/login/' in final_url:
                        return False

            except Exception as e:
                logger.debug(f"🔹 Ошибка проверки Superset {base_url}: {e}")
                continue

        return False

    async def _get_superset_username(self, session_cookie: str) -> str:
        """Получение имени пользователя из Superset"""
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
                            logger.debug(f"🔹 Получено имя пользователя Superset: {username}")
                            return username

            except Exception as e:
                logger.debug(f"🔹 Ошибка получения имени из Superset: {e}")
                continue

        # Запасное значение
        return "Superset User"

    def _is_public_path(self, path: str) -> bool:
        """Проверка, является ли путь публичным"""
        # Полный путь
        if path in self.public_paths:
            return True

        # Путь начинается с публичного префикса
        for public_path in self.public_paths:
            if path.startswith(public_path + "/"):
                return True

        return False

    def _create_superset_redirect(self, request: Request, return_url: str = None) -> RedirectResponse:
        """Создание редиректа на Superset для аутентификации"""
        if not return_url:
            return_url = str(request.url)

        base_url = str(request.base_url)

        # Корректируем URL для продакшена
        if "api.srm-1legion.ru" in base_url:
            base_url = base_url.replace('http://', 'https://')
            return_url = return_url.replace('http://', 'https://')

        login_url = f"{self.superset_url}/login/"
        callback_url = f"{base_url.rstrip('/')}/auth/callback?return_url={return_url}"

        params = {"next": callback_url}
        redirect_url = f"{login_url}?{urlencode(params)}"

        logger.info(f"🔀 Редирект на Superset: {redirect_url}")
        return RedirectResponse(url=redirect_url, status_code=307)