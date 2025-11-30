# middleware.py
from fastapi import Request
from fastapi.responses import RedirectResponse
import httpx
from urllib.parse import urlencode
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from logger_config import logger


class RedirectBasedAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware, который использует редиректы для проверки авторизации
    Не требует доступа к Superset API
    """

    def __init__(self, app: ASGIApp, superset_base_url: str):
        super().__init__(app)
        self.superset_base_url = superset_base_url.rstrip('/')
        self.excluded_paths = [
            "/static",
            "/health",
            "/auth/callback",
            "/logout",
            "/debug/",
            "/auth/verify"
        ]
        # Кэш проверенных сессий (в памяти, для производительности)
        self.verified_sessions = {}

    async def dispatch(self, request: Request, call_next):
        if self._should_exclude_path(request.url.path):
            return await call_next(request)

        logger.info(f"🔐 REDIRECT-BASED проверка для: {request.url.path}")

        session_cookie = request.cookies.get("session")

        if session_cookie:
            # Проверяем в кэше
            if session_cookie in self.verified_sessions:
                if self.verified_sessions[session_cookie]:
                    logger.info("✅ Сессия проверена (кэш), доступ разрешен")
                    return await call_next(request)
                else:
                    logger.warning("❌ Сессия невалидна (кэш)")
            else:
                # Нет в кэше - проверяем через редирект
                is_authenticated = await self._verify_via_redirect(session_cookie, request)
                if is_authenticated:
                    logger.info("✅ Сессия проверена (редирект), доступ разрешен")
                    self.verified_sessions[session_cookie] = True
                    return await call_next(request)
                else:
                    logger.warning("❌ Сессия невалидна (редирект)")
                    self.verified_sessions[session_cookie] = False
        else:
            logger.warning("❌ Куки нет")

        # Редирект на логин
        return self._create_login_redirect(request)

    async def _verify_via_redirect(self, session_cookie: str, request: Request) -> bool:
        """
        Проверяет авторизацию через попытку доступа к защищенной странице Superset
        с последующим анализом редиректа
        """
        try:
            async with httpx.AsyncClient() as client:
                # Пробуем получить защищенную страницу Superset
                test_url = f"{self.superset_base_url}/api/v1/dashboard/"

                response = await client.get(
                    test_url,
                    cookies={"session": session_cookie},
                    timeout=10.0,
                    follow_redirects=False  # Важно: не следовать редиректам
                )

                logger.debug(f"🔹 Проверка редиректа: статус {response.status_code}")

                # Если 200 - авторизован
                if response.status_code == 200:
                    return True

                # Если редирект НЕ на логин - возможно авторизован
                if response.status_code in [301, 302, 307, 308]:
                    location = response.headers.get('location', '')
                    logger.debug(f"🔹 Редирект на: {location}")

                    # Если редирект на логин - неавторизован
                    if '/login/' in location:
                        return False
                    # Другие редиректы - возможно авторизован
                    else:
                        return True

                # 403 - авторизован, но нет прав
                if response.status_code == 403:
                    return True

                # Любой другой статус - считаем неавторизованным
                return False

        except httpx.TimeoutException:
            logger.error("❌ Таймаут при проверке сессии")
            # При таймауте используем fallback-проверку
            return await self._fallback_check(session_cookie)
        except Exception as e:
            logger.error(f"❌ Ошибка проверки через редирект: {e}")
            return await self._fallback_check(session_cookie)

    async def _fallback_check(self, session_cookie: str) -> bool:
        """
        Fallback-проверка когда Superset недоступен
        Проверяем длину и структуру куки как косвенный признак авторизации
        """
        try:
            # Куки гостя обычно короче куки авторизованного пользователя
            # Это эвристика, но лучше чем ничего
            if len(session_cookie) < 100:
                logger.debug("🔹 Fallback: короткая кука (возможно гость)")
                return False
            else:
                logger.debug("🔹 Fallback: длинная кука (возможно авторизован)")
                return True
        except:
            return False

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

        login_url = f"{self.superset_base_url}/login/"
        callback_url = f"{base_url}auth/callback?return_url={return_url}"

        params = {"next": callback_url}
        redirect_url = f"{login_url}?{urlencode(params)}"

        logger.info(f"🔀 Редирект на логин: {redirect_url}")
        return RedirectResponse(url=redirect_url, status_code=307)