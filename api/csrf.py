# api/csrf.py
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.csrf import CSRFMiddleware
import secrets
from typing import Dict, Any
import json

router = APIRouter(prefix="/api/csrf", tags=["csrf"])

# Глобальная переменная для хранения CSRF токенов по сессиям
csrf_store: Dict[str, str] = {}


@router.get("/token")
async def get_csrf_token(request: Request):
    """
    Получение CSRF токена для текущей сессии
    """
    try:
        # Получаем сессию из cookies
        session_id = request.cookies.get("session_id")

        if not session_id:
            # Создаем новую сессию если нет
            session_id = secrets.token_urlsafe(32)

        # Генерируем или получаем существующий токен
        if session_id in csrf_store:
            csrf_token = csrf_store[session_id]
        else:
            csrf_token = secrets.token_urlsafe(32)
            csrf_store[session_id] = csrf_token

            # Очистка старых сессий (можно реализовать при необходимости)
            # clean_old_sessions()

        response = JSONResponse({
            "success": True,
            "csrf_token": csrf_token,
            "session_id": session_id
        })

        # Устанавливаем cookie сессии если её не было
        if not request.cookies.get("session_id"):
            response.set_cookie(
                key="session_id",
                value=session_id,
                httponly=True,
                secure=True,
                max_age=24 * 60 * 60,  # 24 часа
                samesite="strict"
            )

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации CSRF токена: {str(e)}")


@router.post("/validate")
async def validate_csrf_token(request: Request):
    """
    Валидация CSRF токена (используется middleware)
    """
    try:
        data = await request.json()
        csrf_token = data.get("csrf_token")
        session_id = request.cookies.get("session_id")

        if not session_id or not csrf_token:
            raise HTTPException(status_code=400, detail="Недостаточно данных")

        if session_id not in csrf_store:
            raise HTTPException(status_code=400, detail="Сессия не найдена")

        if csrf_store[session_id] != csrf_token:
            raise HTTPException(status_code=403, detail="Неверный CSRF токен")

        return {
            "success": True,
            "message": "CSRF токен валиден"
        }

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Неверный формат JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка валидации: {str(e)}")


@router.post("/rotate")
async def rotate_csrf_token(request: Request):
    """
    Смена CSRF токена для текущей сессии
    """
    try:
        session_id = request.cookies.get("session_id")

        if not session_id:
            raise HTTPException(status_code=400, detail="Сессия не найдена")

        # Генерируем новый токен
        new_csrf_token = secrets.token_urlsafe(32)
        csrf_store[session_id] = new_csrf_token

        return {
            "success": True,
            "csrf_token": new_csrf_token,
            "message": "CSRF токен обновлен"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка смены токена: {str(e)}")


@router.get("/info")
async def csrf_info(request: Request):
    """
    Информация о текущей CSRF сессии (для отладки)
    """
    try:
        session_id = request.cookies.get("session_id")

        info = {
            "session_id": session_id,
            "has_csrf_token": session_id in csrf_store if session_id else False,
            "user_agent": request.headers.get("user-agent", ""),
            "ip_address": request.client.host if request.client else "unknown"
        }

        # Не показываем сам токен в отладочной информации
        if session_id in csrf_store:
            info["csrf_token_length"] = len(csrf_store[session_id])
            info["csrf_token_exists"] = True
        else:
            info["csrf_token_exists"] = False

        return {
            "success": True,
            "info": info
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения информации: {str(e)}")


# Middleware для проверки CSRF токена
class CSRFMiddlewareCustom:
    def __init__(self, app, exempt_paths=None):
        self.app = app
        self.exempt_paths = exempt_paths or [
            "/api/csrf/token",
            "/api/csrf/validate",
            "/api/csrf/rotate",
            "/api/csrf/info",
            "/api/auth/login",
            "/api/auth/register",
            "/health",
            "/static/",
            "/debug/"
        ]

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope, receive)

        # Проверяем, нужно ли проверять CSRF для этого пути
        if any(request.url.path.startswith(path) for path in self.exempt_paths):
            return await self.app(scope, receive, send)

        # Проверяем только POST, PUT, PATCH, DELETE запросы
        if request.method not in ["POST", "PUT", "PATCH", "DELETE"]:
            return await self.app(scope, receive, send)

        try:
            session_id = request.cookies.get("session_id")
            csrf_token = None

            # Ищем CSRF токен в заголовках
            csrf_header = request.headers.get("X-CSRF-Token")

            # Или в теле запроса для form-data
            if not csrf_header and "application/x-www-form-urlencoded" in request.headers.get("content-type", ""):
                body = await request.form()
                csrf_token = body.get("csrf_token")
            # Или в JSON теле
            elif not csrf_header and "application/json" in request.headers.get("content-type", ""):
                body_bytes = await request.body()
                if body_bytes:
                    try:
                        body = json.loads(body_bytes.decode())
                        csrf_token = body.get("csrf_token")
                    except json.JSONDecodeError:
                        pass

            csrf_token = csrf_token or csrf_header

            if not session_id or not csrf_token:
                response = JSONResponse(
                    {"success": False, "error": "CSRF токен отсутствует"},
                    status_code=403
                )
                await response(scope, receive, send)
                return

            if session_id not in csrf_store:
                response = JSONResponse(
                    {"success": False, "error": "Сессия не найдена"},
                    status_code=403
                )
                await response(scope, receive, send)
                return

            if csrf_store[session_id] != csrf_token:
                response = JSONResponse(
                    {"success": False, "error": "Неверный CSRF токен"},
                    status_code=403
                )
                await response(scope, receive, send)
                return

        except Exception as e:
            response = JSONResponse(
                {"success": False, "error": f"Ошибка проверки CSRF: {str(e)}"},
                status_code=500
            )
            await response(scope, receive, send)
            return

        # Если всё ок - пропускаем запрос дальше
        return await self.app(scope, receive, send)