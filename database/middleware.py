# middleware.py
from fastapi import Request
from fastapi.responses import RedirectResponse
import httpx
from urllib.parse import urlencode
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from logger_config import logger
import json
import base64


class StrictRedirectBasedAuthMiddleware(BaseHTTPMiddleware):
    """
    Строгий middleware который надежно проверяет авторизацию
    и получает информацию о пользователе
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
        # Кэш проверенных сессий с информацией о пользователе
        self.verified_sessions = {}

    async def dispatch(self, request: Request, call_next):
        if self._should_exclude_path(request.url.path):
            return await call_next(request)

        logger.info(f"🔐 STRICT проверка для: {request.url.path}")

        session_cookie = request.cookies.get("session")

        if session_cookie:
            # Проверяем в кэше
            if session_cookie in self.verified_sessions:
                cache_data = self.verified_sessions[session_cookie]
                if cache_data["authenticated"]:
                    username = cache_data.get("username", "unknown")
                    logger.info(f"✅ Сессия проверена (кэш), пользователь: {username}")

                    # Добавляем информацию о пользователе в request state
                    request.state.user = cache_data
                    return await call_next(request)
                else:
                    logger.warning("❌ Сессия невалидна (кэш)")
            else:
                # Нет в кэше - проверяем и получаем информацию о пользователе
                auth_result = await self._strict_authentication_check(session_cookie)
                if auth_result["authenticated"]:
                    username = auth_result.get("username", "unknown")
                    logger.info(f"✅ Пользователь авторизован: {username}")

                    # Сохраняем в кэш
                    self.verified_sessions[session_cookie] = auth_result

                    # Добавляем информацию о пользователе в request state
                    request.state.user = auth_result
                    return await call_next(request)
                else:
                    logger.warning("❌ Пользователь не авторизован")
                    self.verified_sessions[session_cookie] = {"authenticated": False}
        else:
            logger.warning("❌ Куки нет")

        # Редирект на логин
        return self._create_login_redirect(request)

    async def _strict_authentication_check(self, session_cookie: str) -> dict:
        """
        Строгая проверка авторизации и получение информации о пользователе
        """
        # Сначала пробуем получить информацию о пользователе через API
        user_info = await self._get_user_info(session_cookie)
        if user_info and user_info.get("authenticated"):
            return user_info

        # Если не удалось получить информацию, пробуем другие методы проверки
        checks = [
            self._check_api_access,
            self._check_main_page,
        ]

        authenticated = False
        for check in checks:
            try:
                result = await check(session_cookie)
                if result is True:
                    authenticated = True
                    break
                elif result is False:
                    authenticated = False
                    break
            except Exception as e:
                logger.debug(f"🔹 Check {check.__name__} error: {e}")
                continue

        # Fallback проверка
        if authenticated is False:
            authenticated = await self._fallback_check(session_cookie)

        return {
            "authenticated": authenticated,
            "username": "unknown",
            "user_id": None,
            "roles": []
        }

    async def _get_user_info(self, session_cookie: str) -> dict:
        """
        Получает информацию о пользователе через Superset API
        """
        try:
            async with httpx.AsyncClient() as client:
                # Пробуем endpoint текущего пользователя
                response = await client.get(
                    f"{self.superset_base_url}/api/v1/security/current",
                    cookies={"session": session_cookie},
                    timeout=8.0,
                    follow_redirects=False
                )

                if response.status_code == 200:
                    user_data = response.json()
                    username = user_data.get('username', 'unknown')
                    user_id = user_data.get('user_id')
                    roles = user_data.get('roles', [])

                    logger.info(f"🔹 Получена информация о пользователе: {username}")

                    return {
                        "authenticated": True,
                        "username": username,
                        "user_id": user_id,
                        "roles": roles,
                        "user_data": user_data
                    }
                else:
                    return None

        except Exception as e:
            logger.debug(f"🔹 Ошибка получения информации о пользователе: {e}")
            return None

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

                if response.status_code == 200:
                    return True
                elif response.status_code == 403:
                    return True
                elif response.status_code == 401:
                    return False
                elif response.status_code in [301, 302, 307, 308]:
                    location = response.headers.get('location', '')
                    if '/login/' in location:
                        return False
                    else:
                        return None
                else:
                    return None

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
                    follow_redirects=True
                )

                final_url = str(response.url)
                if '/login/' in final_url or '/superset/welcome/' in final_url:
                    return False
                else:
                    return True

        except Exception as e:
            logger.debug(f"🔹 Main page check error: {e}")
            return None

    async def _fallback_check(self, session_cookie: str) -> bool:
        """
        Fallback-проверка когда Superset недоступен
        """
        try:
            cookie_length = len(session_cookie)

            if cookie_length < 50:
                logger.debug(f"🔹 Fallback: очень короткая кука ({cookie_length}) - гость")
                return False
            elif cookie_length < 200:
                logger.debug(f"🔹 Fallback: средняя кука ({cookie_length}) - вероятно гость")
                return False
            else:
                logger.debug(f"🔹 Fallback: длинная кука ({cookie_length}) - возможно авторизован")
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