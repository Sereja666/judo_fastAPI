# middleware.py
from fastapi import Request
from fastapi.responses import RedirectResponse
import httpx
from urllib.parse import urlencode
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from logger_config import logger


# middleware.py
class HybridSupersetAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware который:
    - Для проверок авторизации использует ЛОКАЛЬНЫЕ URL (быстро)
    - Для редиректов использует ПУБЛИЧНЫЙ URL (правильные ссылки)
    """

    def __init__(self, app: ASGIApp, superset_base_url: str):
        super().__init__(app)
        self.public_url = superset_base_url.rstrip('/')  # Для редиректов
        self.excluded_paths = [
            "/static",
            "/health",
            "/auth/callback",
            "/logout",
            "/debug/"
        ]

        # Локальные URL для быстрых проверок авторизации
        self.check_urls = [
            "https://localhost:8088",
            "https://172.17.0.1:8088",
            self.public_url  # fallback
        ]

        self.current_check_url = self.check_urls[0]  # Текущий URL для проверок

    async def dispatch(self, request: Request, call_next):
        if self._should_exclude_path(request.url.path):
            return await call_next(request)

        logger.info(f"🔐 HYBRID проверка для: {request.url.path}")

        session_cookie = request.cookies.get("session")

        if session_cookie:
            user_info = await self._check_with_fast_local(session_cookie)

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

    async def _check_with_fast_local(self, session_cookie: str) -> dict:
        """Быстрая проверка авторизации через локальные URL"""
        for check_url in self.check_urls:
            logger.debug(f"🔹 Проверка через: {check_url}")
            user_info = await self._check_single_url(session_cookie, check_url)
            if user_info is not None:  # None = ошибка сети, False = не авторизован
                if user_info.get("authenticated"):
                    # Сохраняем работающий URL для следующих проверок
                    self.current_check_url = check_url
                return user_info

        return None

    async def _check_single_url(self, session_cookie: str, base_url: str) -> dict:
        """Проверка авторизации через конкретный URL"""
        try:
            # Для локальных URL отключаем SSL проверку и используем короткий таймаут
            is_local = base_url.startswith('https://localhost') or base_url.startswith('https://172.17.0.1')
            verify_ssl = not is_local
            timeout = 2.0 if is_local else 8.0

            async with httpx.AsyncClient(verify=verify_ssl) as client:
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
                            return {"authenticated": False}  # Явно не авторизован
                        elif response.status_code in [301, 302, 307, 308]:
                            location = response.headers.get('location', '')
                            if '/login/' in location:
                                return {"authenticated": False}

                    except Exception as e:
                        logger.debug(f"🔹 Ошибка {endpoint} на {base_url}: {e}")
                        continue

                # Если дошли сюда - ошибка сети для этого URL
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
        """Создает редирект на публичный URL Superset"""
        base_url = str(request.base_url)
        return_url = str(request.url)

        if "api.srm-1legion.ru" in base_url:
            base_url = base_url.replace('http://', 'https://')
            return_url = return_url.replace('http://', 'https://')

        # ВСЕГДА используем публичный URL для редиректов
        login_url = f"{self.public_url}/login/"
        callback_url = f"{base_url}auth/callback?return_url={return_url}"

        params = {"next": callback_url}
        redirect_url = f"{login_url}?{urlencode(params)}"

        logger.info(f"🔀 Редирект на публичный Superset: {redirect_url}")
        return RedirectResponse(url=redirect_url, status_code=307)