# middleware.py
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
        self.excluded_paths = ["/static/", "/health", "/auth/callback", "/logout", "/debug/"]

    async def dispatch(self, request: Request, call_next):
        # Пропускаем исключенные пути
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            logger.debug(f"🔹 Пропуск проверки для пути: {request.url.path}")
            return await call_next(request)

        logger.info(f"🔹 Проверка аутентификации для пути: {request.url.path}")

        # Получаем сессионную куку
        session_cookie = request.cookies.get("session")

        logger.info(f"🔹 Сессионная кука: {'есть' if session_cookie else 'нет'}")
        if session_cookie:
            logger.info(f"🔹 Длина куки: {len(session_cookie)} символов")
            logger.debug(f"🔹 Первые 50 символов куки: {session_cookie[:50]}...")

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
                logger.error(f"❌ Критическая ошибка проверки сессии: {e}", exc_info=True)

        # Если куки нет или она невалидна - редирект на логин Superset
        logger.info("🔹 Редирект на страницу логина Superset")

        # Создаем URL для возврата после авторизации
        return_url = str(request.url)
        login_url = f"{self.superset_base_url}/login/"

        # Добавляем параметр next для возврата
        params = {"next": f"{request.base_url}auth/callback?return_url={return_url}"}
        redirect_url = f"{login_url}?{urlencode(params)}"

        logger.debug(f"🔹 URL редиректа: {redirect_url}")
        return RedirectResponse(url=redirect_url)

    async def validate_superset_session(self, session_cookie: str) -> tuple[bool, str]:
        """Проверяет валидность сессии через Superset API"""
        debug_info = ""
        try:
            async with httpx.AsyncClient() as client:
                # Создаем куки для запроса
                cookies = {"session": session_cookie}

                # URL для проверки
                check_url = f"{self.superset_base_url}/api/v1/security/current"
                logger.debug(f"🔹 Проверка сессии через URL: {check_url}")

                # Добавляем заголовки для лучшей совместимости
                headers = {
                    "User-Agent": "StudentManagementSystem/1.0",
                    "Accept": "application/json",
                }

                # Проверяем через endpoint текущего пользователя
                logger.debug("🔹 Отправка запроса к Superset API...")
                response = await client.get(
                    check_url,
                    cookies=cookies,
                    headers=headers,
                    timeout=30.0,  # Увеличиваем таймаут
                    follow_redirects=False
                )

                debug_info = f"Status: {response.status_code}"
                logger.debug(f"🔹 Ответ от Superset: {response.status_code}")

                # Детальный анализ ответа
                if response.status_code == 200:
                    try:
                        user_data = response.json()
                        username = user_data.get('username', 'Unknown')
                        logger.info(f"✅ Авторизованный пользователь: {username}")
                        return True, f"User: {username}"
                    except Exception as e:
                        debug_info = f"JSON parse error: {e}"
                        logger.error(f"❌ Ошибка парсинга JSON ответа: {e}")
                        return False, debug_info

                elif response.status_code == 401:
                    debug_info = "Unauthorized (401) - невалидная сессия"
                    logger.warning("❌ Сессия невалидна (401 Unauthorized)")
                    return False, debug_info

                elif response.status_code == 403:
                    debug_info = "Forbidden (403) - нет доступа к API"
                    logger.warning("❌ Доступ запрещен (403 Forbidden)")
                    return False, debug_info

                elif response.status_code in [301, 302, 307, 308]:
                    location = response.headers.get('location', 'unknown')
                    debug_info = f"Redirect {response.status_code} to {location}"
                    logger.warning(f"🔹 Superset перенаправляет на: {location}")

                    # Если редирект на логин - сессия невалидна
                    if '/login/' in location:
                        debug_info += " (redirect to login)"
                        return False, debug_info
                    else:
                        # Другой редирект - возможно нужно следовать ему
                        debug_info += " (unexpected redirect)"
                        return False, debug_info

                elif response.status_code == 404:
                    debug_info = "API endpoint not found (404)"
                    logger.error("❌ API endpoint не найден (404)")
                    return False, debug_info

                else:
                    # Пробуем получить текст ответа для диагностики
                    try:
                        response_text = response.text[:500]  # Первые 500 символов
                        debug_info = f"Status {response.status_code}: {response_text}"
                        logger.error(f"❌ Неожиданный статус {response.status_code}: {response_text}")
                    except Exception as e:
                        debug_info = f"Status {response.status_code}, cannot read response: {e}"
                        logger.error(f"❌ Неожиданный статус {response.status_code}, ошибка чтения ответа: {e}")

                    return False, debug_info

        except httpx.ConnectError as e:
            debug_info = f"ConnectError: {e}"
            logger.error(f"❌ Не удалось подключиться к Superset: {e}")
            return False, debug_info

        except httpx.TimeoutException as e:
            debug_info = f"Timeout: {e}"
            logger.error(f"❌ Таймаут подключения к Superset (30 сек): {e}")
            return False, debug_info

        except httpx.HTTPError as e:
            debug_info = f"HTTPError: {e}"
            logger.error(f"❌ HTTP ошибка при подключении к Superset: {e}")
            return False, debug_info

        except Exception as e:
            debug_info = f"Unexpected error: {str(e)}"
            logger.error(f"❌ Неожиданная ошибка при проверке сессии Superset: {e}", exc_info=True)
            return False, debug_info


# middleware.py - добавьте этот класс
class DevelopmentAuthMiddleware(BaseHTTPMiddleware):
    """Middleware для разработки - имитирует успешную аутентификацию"""

    def __init__(self, app, superset_base_url: str = None):
        super().__init__(app)
        self.superset_base_url = superset_base_url
        logger.warning("🚨 РЕЖИМ РАЗРАБОТКИ: аутентификация через Superset ОТКЛЮЧЕНА")

    async def dispatch(self, request: Request, call_next):
        # Пропускаем статические файлы и health checks
        if any(request.url.path.startswith(path) for path in ["/static/", "/health", "/debug"]):
            return await call_next(request)

        # Для всех остальных запросов имитируем успешную аутентификацию
        logger.debug(f"🔹 DEV MODE: доступ разрешен для {request.url.path}")

        # Добавляем mock пользователя для использования в роутерах если нужно
        request.state.user = {"username": "dev_user", "id": 1, "email": "dev@example.com"}

        return await call_next(request)