# middleware.py
from fastapi import Request
from fastapi.responses import RedirectResponse
import httpx
from urllib.parse import urlencode
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from logger_config import logger


class SimpleSupersetAuthMiddleware(BaseHTTPMiddleware):
    """
    Простой и надежный middleware для проверки авторизации через Superset API
    """

    def __init__(self, app: ASGIApp, superset_base_url: str):
        super().__init__(app)
        self.superset_base_url = superset_base_url.rstrip('/')
        self.excluded_paths = [
            "/static",
            "/health",
            "/auth/callback",
            "/logout",
            "/debug/"
        ]

    async def dispatch(self, request: Request, call_next):
        # Пропускаем исключенные пути
        if self._should_exclude_path(request.url.path):
            return await call_next(request)

        logger.info(f"🔐 Проверка авторизации для: {request.url.path}")

        # Получаем сессионную куку
        session_cookie = request.cookies.get("session")

        if session_cookie:
            # ПРЯМАЯ ПРОВЕРКА через Superset API
            user_info = await self._check_superset_auth(session_cookie)

            if user_info and user_info.get("authenticated"):
                username = user_info.get("username", "unknown")
                logger.info(f"✅ Пользователь авторизован: {username}")

                # Добавляем информацию о пользователе в request state
                request.state.user = user_info
                return await call_next(request)
            else:
                logger.warning("❌ Пользователь не авторизован в Superset")
        else:
            logger.warning("❌ Сессионная кука отсутствует")

        # Редирект на логин Superset
        return self._create_login_redirect(request)

    async def _check_superset_auth(self, session_cookie: str) -> dict:
        """
        Прямая проверка авторизации через Superset API endpoint /api/v1/me
        """
        try:
            async with httpx.AsyncClient() as client:
                # Используем endpoint /api/v1/me или /api/v1/security/current
                endpoints_to_try = [
                    "/api/v1/me",
                    "/api/v1/security/current",
                    "/api/v1/user/current"  # На всякий случай
                ]

                for endpoint in endpoints_to_try:
                    try:
                        response = await client.get(
                            f"{self.superset_base_url}{endpoint}",
                            cookies={"session": session_cookie},
                            timeout=5.0,  # Короткий таймаут для локального сервера
                            follow_redirects=False
                        )

                        logger.debug(f"🔹 Проверка {endpoint}: статус {response.status_code}")

                        if response.status_code == 200:
                            user_data = response.json()
                            username = user_data.get('username', 'unknown')

                            return {
                                "authenticated": True,
                                "username": username,
                                "user_id": user_data.get('user_id'),
                                "email": user_data.get('email'),
                                "roles": user_data.get('roles', []),
                                "user_data": user_data
                            }

                    except Exception as e:
                        logger.debug(f"🔹 Ошибка при проверке {endpoint}: {e}")
                        continue

                # Если ни один endpoint не сработал
                return None

        except Exception as e:
            logger.error(f"❌ Ошибка проверки авторизации: {e}")
            return None

    def _should_exclude_path(self, path: str) -> bool:
        for excluded in self.excluded_paths:
            if path.startswith(excluded + "/") or path == excluded:
                return True
        return False

    def _create_login_redirect(self, request: Request) -> RedirectResponse:
        base_url = str(request.base_url)
        return_url = str(request.url)

        # Используем HTTPS для продакшн
        if "api.srm-1legion.ru" in base_url:
            base_url = base_url.replace('http://', 'https://')
            return_url = return_url.replace('http://', 'https://')

        login_url = f"{self.superset_base_url}/login/"
        callback_url = f"{base_url}auth/callback?return_url={return_url}"

        params = {"next": callback_url}
        redirect_url = f"{login_url}?{urlencode(params)}"

        logger.info(f"🔀 Редирект на логин Superset: {redirect_url}")
        return RedirectResponse(url=redirect_url, status_code=307)


# middleware.py
class LocalSupersetAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware который пробует локальные URL прежде чем внешние
    """

    def __init__(self, app: ASGIApp, superset_base_url: str):
        super().__init__(app)
        self.original_url = superset_base_url.rstrip('/')
        self.excluded_paths = [
            "/static",
            "/health",
            "/auth/callback",
            "/logout",
            "/debug/"
        ]

        # Генерируем локальные альтернативы
        self.local_urls = self._generate_local_urls()
        self.current_url = self.original_url

    def _generate_local_urls(self) -> list:
        """Генерирует локальные URL для тестирования"""
        from urllib.parse import urlparse
        parsed = urlparse(self.original_url)

        local_urls = []

        # Если оригинальный URL HTTPS, создаем HTTP версии
        if parsed.scheme == 'https':
            base_local = f"http://{parsed.hostname}"
            if parsed.port:
                base_local = f"http://{parsed.hostname}:{parsed.port}"

            local_urls.extend([
                "http://localhost:8088",
                "http://host.docker.internal:8088",
                "http://172.17.0.1:8088",
                "http://superset:8088",
                base_local  # http версия оригинального домена
            ])

        return local_urls

    async def dispatch(self, request: Request, call_next):
        if self._should_exclude_path(request.url.path):
            return await call_next(request)

        logger.info(f"🔐 LOCAL проверка для: {request.url.path}")

        session_cookie = request.cookies.get("session")

        if session_cookie:
            user_info = await self._check_with_local_fallback(session_cookie)

            if user_info and user_info.get("authenticated"):
                username = user_info.get("username", "unknown")
                logger.info(f"✅ Пользователь авторизован: {username}")
                request.state.user = user_info
                return await call_next(request)
            else:
                logger.warning("❌ Пользователь не авторизован")
        else:
            logger.warning("❌ Сессионная кука отсутствует")

        return self._create_login_redirect(request)

    async def _check_with_local_fallback(self, session_cookie: str) -> dict:
        """Проверяет авторизацию с приоритетом локальных URL"""
        # Сначала пробуем локальные URL
        for local_url in self.local_urls:
            logger.debug(f"🔹 Пробуем локальный URL: {local_url}")
            user_info = await self._check_single_url(session_cookie, local_url)
            if user_info:
                logger.info(f"✅ Найден работающий локальный URL: {local_url}")
                self.current_url = local_url
                return user_info

        # Если локальные не работают, пробуем оригинальный URL
        logger.debug(f"🔹 Пробуем оригинальный URL: {self.original_url}")
        user_info = await self._check_single_url(session_cookie, self.original_url)
        if user_info:
            self.current_url = self.original_url
            return user_info

        return None

    async def _check_single_url(self, session_cookie: str, base_url: str) -> dict:
        """Проверка авторизации через конкретный URL"""
        try:
            # Для локальных URL используем более короткий таймаут
            timeout = 3.0 if base_url.startswith('http://') else 10.0

            async with httpx.AsyncClient() as client:
                endpoints = ["/api/v1/me", "/api/v1/security/current"]

                for endpoint in endpoints:
                    try:
                        response = await client.get(
                            f"{base_url}{endpoint}",
                            cookies={"session": session_cookie},
                            timeout=timeout,
                            follow_redirects=False
                        )

                        logger.debug(f"🔹 {base_url}{endpoint}: статус {response.status_code}")

                        if response.status_code == 200:
                            user_data = response.json()
                            return {
                                "authenticated": True,
                                "username": user_data.get('username', 'unknown'),
                                "user_id": user_data.get('user_id'),
                                "email": user_data.get('email'),
                                "roles": user_data.get('roles', []),
                                "user_data": user_data
                            }
                        elif response.status_code == 401:
                            return {"authenticated": False}

                    except Exception as e:
                        logger.debug(f"🔹 Ошибка {endpoint}: {e}")
                        continue

                return None

        except Exception as e:
            logger.debug(f"🔹 Общая ошибка для {base_url}: {e}")
            return None

    def _should_exclude_path(self, path: str) -> bool:
        for excluded in self.excluded_paths:
            if path.startswith(excluded + "/") or path == excluded:
                return True
        return False

    def _create_login_redirect(self, request: Request) -> RedirectResponse:
        base_url = str(request.base_url)
        return_url = str(request.url)

        if "api.srm-1legion.ru" in base_url:
            base_url = base_url.replace('http://', 'https://')
            return_url = return_url.replace('http://', 'https://')

        # Используем текущий работающий URL для редиректа
        login_url = f"{self.current_url}/login/"
        callback_url = f"{base_url}auth/callback?return_url={return_url}"

        params = {"next": callback_url}
        redirect_url = f"{login_url}?{urlencode(params)}"

        logger.info(f"🔀 Редирект на: {redirect_url}")
        return RedirectResponse(url=redirect_url, status_code=307)