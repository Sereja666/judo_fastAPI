# middleware.py
from fastapi import Request
from fastapi.responses import RedirectResponse
import httpx
from urllib.parse import urlencode
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from logger_config import logger



# middleware.py
class SafeSupersetAuthMiddleware(BaseHTTPMiddleware):
    """
    Безопасный middleware:
    - Основная логика проверки авторизации без изменений
    - Получение имени пользователя как дополнительная опция (не блокирующая)
    """

    def __init__(self, app: ASGIApp, superset_base_url: str):
        super().__init__(app)
        self.public_url = superset_base_url.rstrip('/')
        self.excluded_paths = [
            "/static",
            "/health",
            "/auth/callback",
            "/logout",
            "/debug/"
        ]

        self.check_urls = [
            "http://localhost:8088",
            "http://172.17.0.1:8088"
        ]

    async def dispatch(self, request: Request, call_next):
        if self._should_exclude_path(request.url.path):
            return await call_next(request)

        logger.info(f"🔐 SAFE проверка для: {request.url.path}")

        session_cookie = request.cookies.get("session")

        if session_cookie:
            # ОСНОВНАЯ ПРОВЕРКА АВТОРИЗАЦИИ (без изменений)
            is_authenticated = await self._check_auth_safe(session_cookie)

            if is_authenticated:
                # ДОПОЛНИТЕЛЬНО: пытаемся получить имя пользователя (безопасно)
                username = await self._get_username_safe(session_cookie)

                logger.info(f"✅ Пользователь авторизован: {username}")
                request.state.user = {
                    "authenticated": True,
                    "username": username
                }
                return await call_next(request)
            else:
                logger.warning("❌ Пользователь не авторизован")
        else:
            logger.warning("❌ Сессионная кука отсутствует")

        return self._create_login_redirect(request)

    async def _check_auth_safe(self, session_cookie: str) -> bool:
        """ОСНОВНАЯ ПРОВЕРКА АВТОРИЗАЦИИ (без изменений)"""
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

                    # ТА ЖЕ ЛОГИКА что работала
                    if '/login/' not in final_url and response.status_code in [200, 403]:
                        return True

                    if '/login/' in final_url:
                        return False

            except Exception as e:
                logger.debug(f"🔹 {base_url}: ошибка - {e}")
                continue

        return False

    async def _get_username_safe(self, session_cookie: str) -> str:
        """
        БЕЗОПАСНОЕ получение имени пользователя:
        - Не влияет на основную логику авторизации
        - Если не получится - вернет запасное значение
        - Быстрый таймаут
        """
        for base_url in self.check_urls:
            try:
                async with httpx.AsyncClient() as client:
                    # Быстрая попытка получить информацию о пользователе
                    response = await client.get(
                        f"{base_url}/api/v1/me",
                        cookies={"session": session_cookie},
                        timeout=2.0,  # Короткий таймаут
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

        # ЗАПАСНОЕ ЗНАЧЕНИЕ - если не удалось получить имя
        logger.debug("🔹 Используется запасное имя пользователя")
        return "Пользователь"

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

        login_url = f"{self.public_url}/login/"
        callback_url = f"{base_url}auth/callback?return_url={return_url}"

        params = {"next": callback_url}
        redirect_url = f"{login_url}?{urlencode(params)}"

        logger.info(f"🔀 Редирект на публичный Superset: {redirect_url}")
        return RedirectResponse(url=redirect_url, status_code=307)