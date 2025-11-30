# middleware.py - УЛУЧШЕННАЯ версия SupersetAuthMiddleware
from fastapi import Request
from fastapi.responses import RedirectResponse
import httpx
from urllib.parse import urlencode
from starlette.middleware.base import BaseHTTPMiddleware
from logger_config import logger


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