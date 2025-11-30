# middleware.py
from fastapi import Request
from fastapi.responses import RedirectResponse
import httpx
from urllib.parse import urlencode
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from logger_config import logger


class StrictRedirectBasedAuthMiddleware(BaseHTTPMiddleware):
    """
    Строгий middleware который надежно проверяет авторизацию
    и отличает куки гостя от куки авторизованного пользователя
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
        # Кэш проверенных сессий
        self.verified_sessions = {}

    async def dispatch(self, request: Request, call_next):
        if self._should_exclude_path(request.url.path):
            return await call_next(request)

        logger.info(f"🔐 STRICT проверка для: {request.url.path}")

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
                # Нет в кэше - проверяем через несколько методов
                is_authenticated = await self._strict_authentication_check(session_cookie)
                if is_authenticated:
                    logger.info("✅ Пользователь авторизован, доступ разрешен")
                    self.verified_sessions[session_cookie] = True
                    return await call_next(request)
                else:
                    logger.warning("❌ Пользователь не авторизован")
                    self.verified_sessions[session_cookie] = False
        else:
            logger.warning("❌ Куки нет")

        # Редирект на логин
        return self._create_login_redirect(request)

    async def _strict_authentication_check(self, session_cookie: str) -> bool:
        """
        Строгая проверка авторизации через несколько методов
        """
        checks = [
            self._check_api_access,  # Проверка доступа к API
            self._check_main_page,  # Проверка главной страницы
            self._check_user_profile,  # Проверка профиля пользователя
        ]

        results = []
        for check in checks:
            try:
                result = await check(session_cookie)
                results.append(result)
                logger.debug(f"🔹 Check {check.__name__}: {result}")

                # Если хотя бы одна проверка показала False - сразу возвращаем False
                if result is False:
                    return False
                # Если проверка показала True - продолжаем для надежности
                elif result is True:
                    continue

            except Exception as e:
                logger.debug(f"🔹 Check {check.__name__} error: {e}")
                continue

        # Если все проверки прошли или показали True - считаем авторизованным
        if any(results) and not any(r is False for r in results):
            return True

        # Fallback проверка
        return await self._fallback_check(session_cookie)

    async def _check_api_access(self, session_cookie: str) -> bool:
        """Проверка доступа к API дашбордов"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.superset_base_url}/api/v1/dashboard/",
                    cookies={"session": session_cookie},
                    timeout=8.0,
                    follow_redirects=False
                )

                # 200 = авторизован и есть доступ
                if response.status_code == 200:
                    return True
                # 403 = авторизован, но нет прав на дашборды
                elif response.status_code == 403:
                    return True
                # 401 = неавторизован
                elif response.status_code == 401:
                    return False
                # Редирект на логин = неавторизован
                elif response.status_code in [301, 302, 307, 308]:
                    location = response.headers.get('location', '')
                    if '/login/' in location:
                        return False
                    else:
                        return None  # Неопределенный результат
                else:
                    return None  # Неопределенный результат

        except Exception as e:
            logger.debug(f"🔹 API check error: {e}")
            return None

    async def _check_main_page(self, session_cookie: str) -> bool:
        """Проверка доступа к главной странице Superset"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.superset_base_url}/",
                    cookies={"session": session_cookie},
                    timeout=8.0,
                    follow_redirects=True  # Разрешаем редиректы
                )

                final_url = str(response.url)
                # Если после всех редиректов попали на главную страницу (не на логин) - авторизован
                if '/login/' in final_url or '/superset/welcome/' in final_url:
                    return False
                else:
                    return True

        except Exception as e:
            logger.debug(f"🔹 Main page check error: {e}")
            return None

    async def _check_user_profile(self, session_cookie: str) -> bool:
        """Проверка доступа к профилю пользователя"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.superset_base_url}/api/v1/me/",
                    cookies={"session": session_cookie},
                    timeout=8.0,
                    follow_redirects=False
                )

                if response.status_code == 200:
                    return True
                elif response.status_code == 401:
                    return False
                else:
                    return None

        except Exception as e:
            logger.debug(f"🔹 Profile check error: {e}")
            return None

    async def _fallback_check(self, session_cookie: str) -> bool:
        """
        Fallback-проверка когда Superset недоступен
        Использует строгие эвристики
        """
        try:
            # Куки гостя обычно короче и имеют другую структуру
            cookie_length = len(session_cookie)

            # Эвристика 1: очень короткие куки (< 50) - точно гости
            if cookie_length < 50:
                logger.debug(f"🔹 Fallback: очень короткая кука ({cookie_length}) - гость")
                return False

            # Эвристика 2: средние куки (50-200) - подозрительные, считаем гостями
            elif cookie_length < 200:
                logger.debug(f"🔹 Fallback: средняя кука ({cookie_length}) - вероятно гость")
                return False

            # Эвристика 3: длинные куки (> 200) - возможно авторизованный
            else:
                logger.debug(f"🔹 Fallback: длинная кука ({cookie_length}) - возможно авторизован")
                # Но все равно осторожно - лучше запретить доступ
                return False

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