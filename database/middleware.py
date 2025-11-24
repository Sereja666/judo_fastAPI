# middleware.py
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
import httpx
import json

from aiogram import BaseMiddleware
from typing import Callable, Dict, Any, Awaitable
from aiogram.types import TelegramObject, Message
from logger_config import logger




class DBSessionMiddleware(BaseMiddleware):
    """Middleware для управления сессиями базы данных"""

    def __init__(self, session_pool):
        super().__init__()
        self.session_pool = session_pool

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any],
    ) -> Any:
        """Обрабатывает каждый запрос, предоставляя сессию БД"""
        async with self.session_pool() as session:
            data["db_session"] = session
            return await handler(event, data)


class RedisMiddleware(BaseMiddleware):
    """Middleware для добавления Redis в данные хендлеров"""

    def __init__(self, redis_storage):
        super().__init__()
        self.redis_storage = redis_storage

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any],
    ) -> Any:
        """Добавляет redis_storage в данные хендлеров"""
        data["redis_storage"] = self.redis_storage
        return await handler(event, data)


class RateLimitMiddleware(BaseMiddleware):
    """Middleware для ограничения частоты запросов"""

    def __init__(self, redis_storage, limit: int = 5, period: int = 10):
        super().__init__()
        self.redis_storage = redis_storage
        self.limit = limit
        self.period = period

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any],
    ) -> Any:
        """Проверяет rate limit для пользователя"""

        # Применяем только к сообщениям
        if not isinstance(event, Message):
            return await handler(event, data)

        if not self.redis_storage:
            return await handler(event, data)

        user_id = event.from_user.id
        key = f"rate_limit:{user_id}:global"

        try:
            current = await self.redis_storage.redis.get(key)
            if current and int(current) >= self.limit:
                await event.answer("⚠️ Слишком много запросов. Подождите немного.")
                return

            # Увеличиваем счетчик
            pipeline = self.redis_storage.redis.pipeline()
            pipeline.incr(key)
            pipeline.expire(key, self.period)
            await pipeline.execute()

            return await handler(event, data)

        except Exception as e:
            logger.error(f"Rate limit error: {e}")
            return await handler(event, data)


class LoggingMiddleware(BaseMiddleware):
    """Middleware для логирования запросов"""

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any],
    ) -> Any:
        """Логирует входящие запросы"""
        if isinstance(event, Message):
            logger.info(f"Message from {event.from_user.id}: {event.text}")

        return await handler(event, data)


class SupersetAuthMiddleware:
    def __init__(self, app, superset_base_url: str):
        self.app = app
        self.superset_base_url = superset_base_url

    async def __call__(self, request: Request, call_next):
        # Пропускаем статические файлы и health checks
        if any(request.url.path.startswith(path) for path in ["/static/", "/health", "/debug"]):
            return await call_next(request)

        # Получаем сессионную куку
        session_cookie = request.cookies.get("session")

        logger.info(f"🔹 Проверка аутентификации для пути: {request.url.path}")
        logger.info(f"🔹 Сессионная кука: {'есть' if session_cookie else 'нет'}")
        logger.info(f"🔹 Все куки: {dict(request.cookies)}")
        logger.info(f"🔹 Referer: {request.headers.get('referer')}")

        # Если кука есть, проверяем её валидность через Superset API
        if session_cookie:
            try:
                is_valid = await self.validate_superset_session(session_cookie)
                if is_valid:
                    logger.info("✅ Сессия валидна, доступ разрешен")
                    return await call_next(request)
                else:
                    logger.info("❌ Сессия невалидна")
            except Exception as e:
                logger.error(f"❌ Ошибка проверки сессии: {e}")

        # Если куки нет или она невалидна - редирект на логин Superset
        logger.info("🔹 Редирект на страницу логина Superset")
        login_url = f"{self.superset_base_url}/login/?next={request.url}"
        return RedirectResponse(url=login_url)

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
                    timeout=10.0
                )

                if response.status_code == 200:
                    user_data = response.json()
                    logger.info(f"✅ Авторизованный пользователь: {user_data.get('username', 'Unknown')}")
                    return True

                logger.info(f"❌ Superset API вернул статус: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка при проверке сессии Superset: {e}")
            return False