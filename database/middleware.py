# middleware.py
from fastapi import Request
from fastapi.responses import RedirectResponse
import httpx
from urllib.parse import urlencode
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from logger_config import logger


class FinalSupersetAuthMiddleware(BaseHTTPMiddleware):
    """
    Финальный рабочий middleware:
    - Локальные HTTP URL для быстрых проверок
    - Публичный URL для редиректов
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

        # Локальные HTTP URL для проверок (работают!)
        self.check_urls = [
            "http://localhost:8088",
            "http://172.17.0.1:8088"
        ]

    async def dispatch(self, request: Request, call_next):
        if self._should_exclude_path(request.url.path):
            return await call_next(request)

        logger.info(f"🔐 FINAL проверка для: {request.url.path}")

        session_cookie = request.cookies.get("session")

        if session_cookie:
            is_authenticated = await self._check_auth_local_http(session_cookie)

            if is_authenticated:
                logger.info("✅ Пользователь авторизован")
                request.state.user = {"authenticated": True, "username": "user"}
                return await call_next(request)
            else:
                logger.warning("❌ Пользователь не авторизован")
        else:
            logger.warning("❌ Сессионная кука отсутствует")

        return self._create_login_redirect(request)

    async def _check_auth_local_http(self, session_cookie: str) -> bool:
        """Проверка авторизации через локальные HTTP URL"""
        for base_url in self.check_urls:
            try:
                async with httpx.AsyncClient() as client:
                    # Пробуем endpoint который требует авторизации
                    response = await client.get(
                        f"{base_url}/api/v1/dashboard/",
                        cookies={"session": session_cookie},
                        timeout=3.0,  # Короткий таймаут для локальных
                        follow_redirects=True  # Разрешаем редиректы
                    )

                    final_url = str(response.url)
                    logger.debug(f"🔹 {base_url}: final URL = {final_url}, status = {response.status_code}")

                    # Критерии авторизации:
                    # - Нет редиректа на /login/
                    # - Статус код 200 или 403 (авторизован, но нет прав)
                    if '/login/' not in final_url and response.status_code in [200, 403]:
                        logger.info(f"✅ Авторизация подтверждена через {base_url}")
                        return True

                    # Если явно редирект на логин - не авторизован
                    if '/login/' in final_url:
                        logger.debug(f"🔹 {base_url}: редирект на логин")
                        return False

            except Exception as e:
                logger.debug(f"🔹 {base_url}: ошибка - {e}")
                continue

        return False

    def _should_exclude_path(self, path: str) -> bool:
        for excluded in self.excluded_paths:
            if path.startswith(excluded + "/") or path == excluded:
                return True
        return False

    def _create_login_redirect(self, request: Request) -> RedirectResponse:
        """Редирект на публичный URL Superset"""
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