# middleware.py
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
import httpx
import json
from urllib.parse import urlparse, urlencode
from logger_config import logger


class SupersetAuthMiddleware:
    def __init__(self, app, superset_base_url: str):
        self.app = app
        self.superset_base_url = superset_base_url.rstrip('/')
        self.excluded_paths = ["/static/", "/health", "/auth/callback", "/logout"]

    async def __call__(self, request: Request, call_next):
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
                is_valid = await self.validate_superset_session(session_cookie)
                if is_valid:
                    logger.info("✅ Сессия валидна, доступ разрешен")
                    return await call_next(request)
                else:
                    logger.info("❌ Сессия невалидна, удаляем куку")
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

    async def validate_superset_session(self, session_cookie: str) -> bool:
        """Проверяет валидность сессии через Superset API"""
        try:
            async with httpx.AsyncClient() as client:
                # Создаем куки для запроса
                cookies = {"session": session_cookie}

                # Проверяем через endpoint текущего пользователя
                response = await client.get(
                    f"{self.superset_base_url}/api/v1/security/current",
                    cookies=cookies,
                    timeout=10.0,
                    follow_redirects=True
                )

                if response.status_code == 200:
                    user_data = response.json()
                    username = user_data.get('username', 'Unknown')
                    logger.info(f"✅ Авторизованный пользователь: {username}")
                    return True

                logger.info(f"❌ Superset API вернул статус: {response.status_code}")
                return False

        except httpx.ConnectError:
            logger.error("❌ Не удалось подключиться к Superset")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке сессии Superset: {e}")
            return False