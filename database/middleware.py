from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
import httpx
from urllib.parse import urlencode, urlparse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Scope, Receive, Send
from logger_config import logger

class StrictSupersetAuthMiddleware(BaseHTTPMiddleware):
    """
    Строгий middleware - всегда требует авторизацию через Superset
    Работает на уровне ASGI для надежности
    """

    def __init__(self, app: ASGIApp, superset_base_url: str):
        super().__init__(app)
        self.superset_base_url = superset_base_url.rstrip('/')
        # Более строгий список исключений - только то, что действительно нужно
        self.excluded_paths = [
            "/static",  # Без слеша в конце, чтобы ловило /static/...
            "/health",
            "/auth/callback",
            "/logout",
            "/debug/superset-status",
            "/debug/middleware-check"
        ]

    async def dispatch(self, request: Request, call_next):
        # Логируем ВСЕ запросы для отладки
        logger.debug(f"🔄 Middleware получил запрос: {request.method} {request.url.path}")

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
        # Точное совпадение
        if path in self.excluded_paths:
            return True

        # Пути, начинающиеся с исключенных префиксов
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
                    except:
                        logger.warning("⚠️ Не удалось распарсить ответ Superset")
                        return False

                # Если редирект на логин - сессия невалидна
                if response.status_code in [301, 302, 307, 308]:
                    location = response.headers.get('location', '')
                    if '/login/' in location:
                        logger.info("🔹 Superset перенаправляет на логин - сессия невалидна")
                        return False

                return False

        except httpx.ConnectError:
            logger.error("❌ Не удалось подключиться к Superset")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка проверки сессии: {e}")
            return False

    def _create_login_redirect(self, request: Request) -> RedirectResponse:
        """Создает редирект на страницу логина Superset"""
        return_url = str(request.url)
        login_url = f"{self.superset_base_url}/login/"

        # Кодируем URL для возврата после авторизации
        callback_url = f"{request.base_url}auth/callback?return_url={return_url}"
        params = {"next": callback_url}
        redirect_url = f"{login_url}?{urlencode(params)}"

        logger.info(f"🔀 Редирект на: {redirect_url}")
        return RedirectResponse(url=redirect_url, status_code=307)


class SupersetAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, superset_base_url: str):
        super().__init__(app)
        self.superset_base_url = superset_base_url.rstrip('/')
        self.excluded_paths = ["/static/", "/health", "/auth/callback", "/logout", "/debug/superset-test"]
        self.superset_available = True  # Предполагаем, что доступен

    async def dispatch(self, request: Request, call_next):
        # Пропускаем исключенные пути
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            return await call_next(request)

        logger.info(f"🔹 Проверка аутентификации для пути: {request.url.path}")

        # Получаем сессионную куку
        session_cookie = request.cookies.get("session")

        logger.info(f"🔹 Сессионная кука: {'есть' if session_cookie else 'нет'}")

        # Если кука есть, проверяем её валидность через Superset API
        if session_cookie:
            try:
                is_valid, debug_info = await self.validate_superset_session(session_cookie)
                if is_valid:
                    logger.info("✅ Сессия валидна, доступ разрешен")
                    return await call_next(request)
                else:
                    logger.warning(f"❌ Сессия невалидна: {debug_info}")
            except Exception as e:
                logger.error(f"❌ Ошибка проверки сессии: {e}")

        # Если куки нет или она невалидна - редирект на логин Superset
        logger.info("🔹 Редирект на страницу логина Superset")

        # Создаем URL для возврата после авторизации
        return_url = str(request.url)
        login_url = f"{self.superset_base_url}/login/"

        # Добавляем параметр next для возврата
        params = {"next": f"{request.base_url}auth/callback?return_url={return_url}"}
        redirect_url = f"{login_url}?{urlencode(params)}"

        return RedirectResponse(url=redirect_url)

    async def validate_superset_session(self, session_cookie: str) -> tuple[bool, str]:
        """Проверяет валидность сессии через Superset API с улучшенной обработкой ошибок"""
        debug_info = ""
        try:
            async with httpx.AsyncClient() as client:
                # Создаем куки для запроса
                cookies = {"session": session_cookie}

                # Пробуем несколько endpoint'ов Superset
                endpoints_to_try = [
                    "/api/v1/security/current",
                    "/api/v1/me/",  # Альтернативный endpoint
                    "/login/",  # Если редиректит на логин - сессия невалидна
                ]

                for endpoint in endpoints_to_try:
                    check_url = f"{self.superset_base_url}{endpoint}"
                    logger.debug(f"🔹 Попытка проверки через: {check_url}")

                    try:
                        response = await client.get(
                            check_url,
                            cookies=cookies,
                            timeout=10.0,
                            follow_redirects=False
                        )

                        logger.debug(f"🔹 Ответ от {endpoint}: {response.status_code}")

                        if response.status_code == 200 and endpoint != "/login/":
                            # Успешная аутентификация
                            try:
                                user_data = response.json()
                                username = user_data.get('username', 'Unknown')
                                logger.info(f"✅ Авторизованный пользователь: {username}")
                                return True, f"User: {username}"
                            except:
                                # Если не JSON, но 200 - возможно главная страница
                                continue

                        elif response.status_code in [301, 302, 307, 308]:
                            location = response.headers.get('location', '')
                            if '/login/' in location:
                                logger.info("🔹 Редирект на логин - сессия невалидна")
                                return False, "Redirect to login"
                            else:
                                continue

                        elif response.status_code == 401:
                            return False, "Unauthorized"

                    except Exception as e:
                        logger.debug(f"🔹 Ошибка при проверке {endpoint}: {e}")
                        continue

                # Если ни один endpoint не сработал
                return False, "All endpoints failed"

        except httpx.ConnectError as e:
            debug_info = f"ConnectError: {e}"
            logger.error(f"❌ Не удалось подключиться к Superset")
            # Если не можем подключиться к Superset, НЕ пропускаем пользователя
            return False, "Superset unavailable"

        except Exception as e:
            debug_info = f"Exception: {str(e)}"
            logger.error(f"❌ Ошибка при проверке сессии Superset: {e}")
            return False, debug_info