# api_main.py - ОБНОВЛЕННЫЙ
import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import httpx

# Импортируем middleware
from database.middleware import SafeSupersetAuthMiddleware
from config import settings

# Импортируем существующие роутеры
from api.students import router as students_router
from api.schedule import router as schedule_router
from api.trainers import router as trainers_router
from api.tg_membership import router as admin_router
from api.visits import router as visits_router
from api.competitions import router as competitions_router
# Импортируем новый роутер для локальной аутентификации
from api.local_auth import router as local_auth_router

from config import templates
from logger_config import logger

app = FastAPI(
    title="Student Management System",
    description="Система управления спортивной школой 'Первый Легион'",
    version="1.0.0"
)

# Монтируем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")

# URL вашего Superset
SUPERSET_BASE_URL = settings.superset_conf.base_url

# Подключаем middleware для двойной аутентификации
app.add_middleware(SafeSupersetAuthMiddleware, superset_base_url=SUPERSET_BASE_URL)

# Подключаем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене укажите конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(schedule_router, prefix="/schedule", tags=["schedule"])
app.include_router(students_router, tags=["students"])
app.include_router(trainers_router, tags=["trainers"])
app.include_router(visits_router, tags=["visits"])
app.include_router(competitions_router, tags=["competitions"])
app.include_router(admin_router, tags=["admin"])
# Подключаем роутер локальной аутентификации
app.include_router(local_auth_router)


# ========== ОСНОВНЫЕ ЭНДПОИНТЫ ==========

@app.get("/health")
async def health_check():
    """Эндпоинт для проверки здоровья приложения"""
    return {
        "status": "healthy",
        "service": "Student Management System",
        "version": "1.0.0",
        "auth_systems": ["superset", "local_jwt"]
    }


@app.get("/auth/callback")
async def auth_callback(request: Request, return_url: str = "/"):
    """Callback endpoint для обработки редиректа после авторизации Superset"""
    session_cookie = request.cookies.get("session")

    logger.info(f"🔹 Auth callback получен, return_url: {return_url}")

    if session_cookie:
        # Проверяем, что сессия действительно валидна
        from database.middleware import SafeSupersetAuthMiddleware
        checker = SafeSupersetAuthMiddleware(app=None, superset_base_url=SUPERSET_BASE_URL)
        user_info = await checker._get_superset_user(request)

        if user_info and user_info.get("authenticated"):
            safe_return_url = return_url.replace('http://', 'https://')

            response = RedirectResponse(url=safe_return_url)
            response.set_cookie(
                key="session",
                value=session_cookie,
                httponly=True,
                secure=True,
                max_age=24 * 60 * 60,
                samesite="lax"
            )
            logger.info(f"✅ Успешная аутентификация Superset: {user_info.get('username')}")
            return response

    logger.warning("⚠️ Неудачная аутентификация в callback")
    safe_login_url = f"{SUPERSET_BASE_URL}/login/"
    return RedirectResponse(url=safe_login_url)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Страница выбора метода аутентификации"""
    superset_login_url = f"{SUPERSET_BASE_URL}/login/"

    return templates.TemplateResponse("login.html", {
        "request": request,
        "superset_login_url": superset_login_url
    })


@app.get("/logout")
async def logout(request: Request):
    """Выход из системы (удаляет все сессии)"""
    response = RedirectResponse(url="/login")

    # Определяем метод аутентификации
    user_info = getattr(request.state, 'user', None)
    auth_method = user_info.get("auth_method") if user_info else None

    # Удаляем все возможные сессионные куки
    cookies_to_delete = ["session", "local_session"]

    for cookie_name in cookies_to_delete:
        response.delete_cookie(cookie_name, path="/")

    # Если это была Superset сессия, делаем logout из Superset
    if auth_method == "superset":
        superset_logout_url = f"{SUPERSET_BASE_URL}/logout/"
        response = RedirectResponse(url=superset_logout_url)
        for cookie_name in cookies_to_delete:
            response.delete_cookie(cookie_name, path="/")

    logger.info(f"🚪 Выход из системы (метод: {auth_method or 'неизвестен'})")
    return response


@app.get("/debug/auth-status")
async def debug_auth_status(request: Request):
    """Проверка текущего статуса авторизации"""
    user_info = getattr(request.state, 'user', None)

    if user_info and user_info.get("authenticated"):
        return {
            "authenticated": True,
            "auth_method": user_info.get("auth_method"),
            "username": user_info.get("username"),
            "email": user_info.get("email"),
            "full_name": user_info.get("full_name"),
            "is_superuser": user_info.get("is_superuser", False),
            "message": f"Авторизован как {user_info.get('username')}",
            "cookies_present": {
                "session": bool(request.cookies.get("session")),
                "local_session": bool(request.cookies.get("local_session"))
            }
        }
    else:
        return {
            "authenticated": False,
            "message": "Не авторизован",
            "available_methods": ["superset", "local_jwt"],
            "login_url": "/login"
        }


@app.get("/debug/test-superset-connection")
async def debug_test_superset_connection():
    """Тест подключения к Superset API"""
    try:
        async with httpx.AsyncClient() as client:
            endpoints = [
                "/api/v1/me",
                "/api/v1/security/current",
                "/api/v1/user/current"
            ]

            results = {}
            for endpoint in endpoints:
                try:
                    response = await client.get(
                        f"{SUPERSET_BASE_URL}{endpoint}",
                        timeout=3.0
                    )
                    results[endpoint] = {
                        "status_code": response.status_code,
                        "headers": dict(response.headers)
                    }
                except Exception as e:
                    results[endpoint] = {"error": str(e)}

            return {
                "superset_url": SUPERSET_BASE_URL,
                "connection_test": results,
                "status": "success" if any(r.get("status_code") == 200 for r in results.values()) else "failed"
            }
    except Exception as e:
        return {"error": str(e), "status": "failed"}


@app.get("/debug/test-local-auth")
async def debug_test_local_auth():
    """Тест локальной аутентификации"""
    from api.local_auth import TEMP_USERS_DB

    return {
        "status": "ok",
        "local_auth_enabled": settings.enable_local_auth,
        "available_test_users": list(TEMP_USERS_DB.keys()),
        "test_credentials": [
            {"username": "admin", "password": "admin123"},
            {"username": "trainer", "password": "trainer123"},
            {"username": "user", "password": "user123"}
        ]
    }


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Главная страница системы"""
    user_info = getattr(request.state, 'user', None)

    if user_info and user_info.get("authenticated"):
        username = user_info.get("username", "Пользователь")
        auth_method = user_info.get("auth_method", "unknown")

        return templates.TemplateResponse("home.html", {
            "request": request,
            "user_authenticated": True,
            "username": username,
            "auth_method": auth_method
        })
    else:
        # Если не авторизован, показываем домашнюю страницу с возможностью входа
        return templates.TemplateResponse("home.html", {
            "request": request,
            "user_authenticated": False,
            "username": None,
            "auth_method": None
        })


# ========== ЗАПУСК СЕРВЕРА ==========

if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 Запуск сервера с системой двойной аутентификации")
    logger.info(f"📊 Superset URL: {SUPERSET_BASE_URL}")
    logger.info(f"🔐 Локальная аутентификация: {'ВКЛЮЧЕНА' if settings.enable_local_auth else 'ВЫКЛЮЧЕНА'}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_config=None,
        proxy_headers=True
    )