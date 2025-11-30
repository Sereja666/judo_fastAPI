# middleware.py
from fastapi import Request
from fastapi.responses import RedirectResponse
import httpx
from urllib.parse import urlencode
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from logger_config import logger


# middleware.py
class WorkingSupersetAuthMiddleware(BaseHTTPMiddleware):
    """
    Упрощенный middleware который работает с текущей конфигурацией Superset
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

        # URL для проверок авторизации (пробуем разные варианты)
        self.check_urls = [
            "http://localhost:8088",  # Локальный HTTP
            "http://172.17.0.1:8088",  # Docker HTTP
            self.public_url,  # Публичный HTTPS
            self.public_url.replace('https', 'http'),  # Публичный HTTP
        ]

    async def dispatch(self, request: Request, call_next):
        if self._should_exclude_path(request.url.path):
            return await call_next(request)

        logger.info(f"🔐 WORKING проверка для: {request.url.path}")

        session_cookie = request.cookies.get("session")

        if session_cookie:
            user_info = await self._simple_auth_check(session_cookie)

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

    async def _simple_auth_check(self, session_cookie: str) -> dict:
        """Простая проверка авторизации"""
        for base_url in self.check_urls:
            logger.debug(f"🔹 Проверка через: {base_url}")

            try:
                # Отключаем SSL проверку для всех URL
                async with httpx.AsyncClient(verify=False) as client:
                    # Пробуем endpoint который требует авторизации
                    response = await client.get(
                        f"{base_url}/api/v1/dashboard/",
                        cookies={"session": session_cookie},
                        timeout=5.0,
                        follow_redirects=True  # Разрешаем редиректы
                    )

                    final_url = str(response.url)
                    logger.debug(f"🔹 Final URL: {final_url}, Status: {response.status_code}")

                    # Если после редиректов попали на страницу с дашбордами (не на логин) - авторизован
                    if '/login/' not in final_url and response.status_code != 401:
                        # Дополнительная проверка - пробуем получить информацию о пользователе
                        user_info = await self._get_user_info(session_cookie, base_url)
                        if user_info:
                            return user_info
                        else:
                            return {"authenticated": True, "username": "unknown"}  # Эвристика

                    # Если редирект на логин - не авторизован
                    if '/login/' in final_url:
                        return {"authenticated": False}

            except Exception as e:
                logger.debug(f"🔹 Ошибка для {base_url}: {e}")
                continue

        return None

    async def _get_user_info(self, session_cookie: str, base_url: str) -> dict:
        """Пытается получить информацию о пользователе"""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                endpoints = ["/api/v1/me", "/api/v1/security/current"]

                for endpoint in endpoints:
                    try:
                        response = await client.get(
                            f"{base_url}{endpoint}",
                            cookies={"session": session_cookie},
                            timeout=3.0,
                            follow_redirects=False
                        )

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
                    except:
                        continue
        except:
            pass

        return None

    def _should_exclude_path(self, path: str) -> bool:
        for excluded in self.excluded_paths:
            if path.startswith(excluded + "/") or path == excluded:
                return True
        return False

    def _create_login_redirect(self, request: Request) -> RedirectResponse:
        """Создает редирект на публичный URL"""
        base_url = str(request.base_url)
        return_url = str(request.url)

        if "api.srm-1legion.ru" in base_url:
            base_url = base_url.replace('http://', 'https://')
            return_url = return_url.replace('http://', 'https://')

        login_url = f"{self.public_url}/login/"
        callback_url = f"{base_url}auth/callback?return_url={return_url}"

        params = {"next": callback_url}
        redirect_url = f"{login_url}?{urlencode(params)}"

        logger.info(f"🔀 Редирект на: {redirect_url}")
        return RedirectResponse(url=redirect_url, status_code=307)