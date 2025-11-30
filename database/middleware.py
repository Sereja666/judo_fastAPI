# middleware.py
from fastapi import Request
from fastapi.responses import RedirectResponse
import httpx
from urllib.parse import urlencode
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from logger_config import logger


# middleware.py
class SmartCookieAuthMiddleware(BaseHTTPMiddleware):
    """
    Умный middleware - проверяет не просто наличие куки, а факт авторизации в Superset
    через проверку доступности защищенных страниц
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
        if self._should_exclude_path(request.url.path):
            return await call_next(request)

        logger.info(f"🔐 SMART проверка для: {request.url.path}")

        session_cookie = request.cookies.get("session")

        if session_cookie:
            # Проверяем, это кука авторизованного пользователя или гостя
            is_authenticated = await self._check_if_authenticated(session_cookie)
            if is_authenticated:
                logger.info("✅ Пользователь авторизован в Superset, доступ разрешен")
                return await call_next(request)
            else:
                logger.warning("❌ Кука есть, но пользователь не авторизован в Superset")
        else:
            logger.warning("❌ Куки нет")

        # Редирект на логин
        return self._create_login_redirect(request)

    async def _check_if_authenticated(self, session_cookie: str) -> bool:
        """
        Проверяет, авторизован ли пользователь в Superset
        путем проверки доступа к защищенным ресурсам
        """
        try:
            async with httpx.AsyncClient() as client:
                # Пробуем получить дашборды - доступно только авторизованным
                dashboards_url = f"{self.superset_base_url}/api/v1/dashboard/"

                response = await client.get(
                    dashboards_url,
                    cookies={"session": session_cookie},
                    timeout=10.0,
                    follow_redirects=False
                )

                logger.debug(f"🔹 Проверка авторизации: статус {response.status_code}")

                # 200 = авторизован и есть доступ к API
                if response.status_code == 200:
                    return True

                # 302/redirect на логин = неавторизован
                if response.status_code in [301, 302, 307, 308]:
                    location = response.headers.get('location', '')
                    if '/login/' in location:
                        return False

                # 403 = авторизован, но нет прав (все равно авторизован!)
                if response.status_code == 403:
                    return True

                # 401 = неавторизован
                if response.status_code == 401:
                    return False

                # Другие статусы - осторожно, считаем неавторизованным
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка проверки авторизации: {e}")
            # Если не можем проверить - считаем неавторизованным (безопаснее)
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

class StrictSupersetAuthMiddleware(BaseHTTPMiddleware):
    """
    Строгий middleware - всегда требует авторизацию через Superset
    """

    def __init__(self, app: ASGIApp, superset_base_url: str):
        super().__init__(app)
        self.superset_base_url = superset_base_url.rstrip('/')
        self.excluded_paths = [
            "/static",
            "/health",
            "/auth/callback",
            "/logout",
            "/debug/superset-status",
            "/debug/middleware-check",
            "/debug/request-info"
        ]

    async def dispatch(self, request: Request, call_next):
        # Логируем запрос для отладки
        logger.debug(f"🔄 Middleware: {request.method} {request.url.path}")

        # Проверяем, нужно ли исключить путь
        if self._should_exclude_path(request.url.path):
            logger.debug(f"🔹 Пропускаем исключенный путь: {request.url.path}")
            return await call_next(request)

        logger.info(f"🔐 Проверка аутентификации для: {request.url.path}")

        # Получаем сессионную куку
        session_cookie = request.cookies.get("session")
        logger.info(f"🔹 Сессионная кука: {'ЕСТЬ' if session_cookie else 'НЕТ'}")

        # Если есть кука, проверяем её
        if session_cookie:
            is_valid = await self._validate_session(session_cookie)
            if is_valid:
                logger.info("✅ Сессия валидна, доступ разрешен")
                return await call_next(request)
            else:
                logger.warning("❌ Сессия невалидна")
        else:
            logger.warning("❌ Сессионная кука отсутствует")

        # Если дошли сюда - редирект на логин
        logger.info(f"🔀 Редирект на логин Superset с пути: {request.url.path}")
        return self._create_login_redirect(request)

    def _should_exclude_path(self, path: str) -> bool:
        """Проверяет, нужно ли исключить путь из проверки аутентификации"""
        for excluded in self.excluded_paths:
            if path.startswith(excluded + "/") or path == excluded:
                return True
        return False

    async def _validate_session(self, session_cookie: str) -> bool:
        """Проверяет валидность сессии"""
        try:
            async with httpx.AsyncClient() as client:
                # Пробуем основной endpoint
                response = await client.get(
                    f"{self.superset_base_url}/api/v1/security/current",
                    cookies={"session": session_cookie},
                    timeout=10.0,
                    follow_redirects=False
                )

                logger.debug(f"🔹 Ответ от Superset: {response.status_code}")

                if response.status_code == 200:
                    try:
                        user_data = response.json()
                        username = user_data.get('username', 'unknown')
                        logger.info(f"✅ Авторизован пользователь: {username}")
                        return True
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось распарсить ответ Superset: {e}")
                        # Но все равно считаем валидным, так как статус 200
                        return True

                # Если редирект на логин - сессия невалидна
                if response.status_code in [301, 302, 307, 308]:
                    location = response.headers.get('location', '')
                    if '/login/' in location:
                        logger.info("🔹 Superset перенаправляет на логин - сессия невалидна")
                        return False

                logger.warning(f"🔹 Superset вернул статус: {response.status_code}")
                return False

        except httpx.ConnectError:
            logger.error("❌ Не удалось подключиться к Superset")
            return False
        except httpx.TimeoutException:
            logger.error("❌ Таймаут подключения к Superset")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка проверки сессии: {e}")
            return False

    def _create_login_redirect(self, request: Request) -> RedirectResponse:
        """Создает редирект на страницу логина Superset"""
        # Используем HTTPS URL для callback
        base_url = str(request.base_url)
        return_url = str(request.url)

        # Принудительно используем HTTPS если это продакшн
        if "api.srm-1legion.ru" in base_url:
            base_url = base_url.replace('http://', 'https://')
            return_url = return_url.replace('http://', 'https://')

        login_url = f"{self.superset_base_url}/login/"
        callback_url = f"{base_url}auth/callback?return_url={return_url}"

        params = {"next": callback_url}
        redirect_url = f"{login_url}?{urlencode(params)}"

        logger.info(f"🔀 Редирект на: {redirect_url}")
        return RedirectResponse(url=redirect_url, status_code=307)



class CookieOnlyAuthMiddleware(BaseHTTPMiddleware):
    """
    Упрощенный middleware - проверяет только наличие куки, без проверки в Superset
    ИСПОЛЬЗУЙТЕ ТОЛЬКО ДЛЯ ТЕСТИРОВАНИЯ!
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
        if self._should_exclude_path(request.url.path):
            return await call_next(request)

        logger.info(f"🔐 COOKIE-ONLY проверка для: {request.url.path}")

        # Просто проверяем наличие куки, без проверки в Superset
        session_cookie = request.cookies.get("session")

        if session_cookie:
            logger.info("✅ Кука есть, доступ разрешен (без проверки в Superset)")
            return await call_next(request)
        else:
            logger.warning("❌ Куки нет, редирект на логин")
            return self._create_login_redirect(request)

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

        logger.info(f"🔀 Редирект на: {redirect_url}")
        return RedirectResponse(url=redirect_url, status_code=307)

# Резервный middleware для отладки (не использовать в продакшн)
class TestAuthMiddleware(BaseHTTPMiddleware):
    """Простой тестовый middleware для проверки работы"""

    async def dispatch(self, request: Request, call_next):
        logger.info(f"🚨 TEST MIDDLEWARE: Запрос к {request.url.path}")

        # Блокируем ВСЕ запросы кроме статических и debug
        if not any(request.url.path.startswith(path) for path in ["/static/", "/debug/", "/health"]):
            logger.info("🚨 TEST: Блокируем запрос!")
            from fastapi.responses import JSONResponse
            return JSONResponse(
                {"error": "Доступ запрещен - middleware работает!", "path": request.url.path},
                status_code=403
            )

        return await call_next(request)


# middleware.py
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