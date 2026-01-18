import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import httpx

# Импортируем упрощенный middleware
from database.middleware import DualAuthMiddleware
from database.middleware import SimpleCSRFProtection
from config import settings

# Импортируем роутеры
from api.students import router as students_router
from api.schedule import router as schedule_router
from api.trainers import router as trainers_router

from api.tg_membership import router as admin_router
from api.visits import router as visits_router
from api.competitions import router as competitions_router
from api.auth import router as auth_router
from api.visits_today import router as visits_today_router
from config import templates
from logger_config import logger

app = FastAPI(title="Student Management System")
app.add_middleware(SimpleCSRFProtection)
# Монтируем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")

# URL вашего Superset
SUPERSET_BASE_URL = settings.superset_conf.base_url


# СОЗДАЕМ ПУБЛИЧНЫЕ МАРШРУТЫ ДО ПОДКЛЮЧЕНИЯ MIDDLEWARE
@app.get("/choose-login", include_in_schema=False)
async def choose_login_page(request: Request):
    """Страница выбора способа входа"""
    superset_base_url = SUPERSET_BASE_URL.rstrip('/')
    callback_url = f"{request.base_url}auth/callback?return_url={request.base_url}"
    superset_login_url = f"{superset_base_url}/login/?next={callback_url}"

    return templates.TemplateResponse("choose_login.html", {
        "request": request,
        "superset_login_url": superset_login_url
    })


@app.get("/local-login", include_in_schema=False)
async def local_login_page(request: Request):
    """Страница локального входа"""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "superset_url": SUPERSET_BASE_URL
    })


# Только после этого подключаем middleware
app.add_middleware(DualAuthMiddleware, superset_base_url=SUPERSET_BASE_URL)

# Подключаем роутеры
app.include_router(schedule_router, prefix="/schedule", tags=["schedule"])
app.include_router(students_router, tags=["students"])
app.include_router(trainers_router, tags=["trainers"])
app.include_router(visits_router, tags=["visits"])
app.include_router(competitions_router, tags=["competitions"])
app.include_router(admin_router, tags=["admin"])
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])  # Оставляем /api/auth для API
app.include_router(visits_today_router, tags=["visits-today"])



@app.get("/health")
async def health_check():
    """Эндпоинт для проверки здоровья приложения"""
    return {"status": "healthy", "service": "Student Management System"}

@app.get("/auth/callback")
async def auth_callback(request: Request, return_url: str = "/"):
    """Callback endpoint для обработки редиректа после авторизации Superset"""
    session_cookie = request.cookies.get("session")

    logger.info(f"🔹 Auth callback received, return_url: {return_url}")

    if session_cookie:
        # Проверяем, что сессия действительно валидна
        from database.middleware import DualAuthMiddleware
        checker = DualAuthMiddleware(app=None, superset_base_url=SUPERSET_BASE_URL)
        user_info = await checker._authenticate_superset(session_cookie)

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
            logger.info(f"✅ Успешная аутентификация: {user_info.get('username')}")
            return response

    logger.warning("⚠️ Неудачная аутентификация в callback")
    safe_login_url = f"{SUPERSET_BASE_URL}/login/"
    return RedirectResponse(url=safe_login_url)


@app.get("/logout")
async def logout(request: Request):
    """Универсальный выход из системы"""
    # Определяем тип авторизации
    user_info = getattr(request.state, 'user', None)
    auth_type = user_info.get("auth_type") if user_info else None

    response = RedirectResponse(url="/choose-login")

    # Удаляем ВСЕ возможные авторизационные cookies
    response.delete_cookie("session")  # Superset
    response.delete_cookie("access_token")  # JWT

    # Также можно удалить через JavaScript localStorage
    return response


@app.get("/debug/auth-status")
async def debug_auth_status(request: Request):
    """Проверка текущего статуса авторизации"""
    user_info = getattr(request.state, 'user', None)

    if user_info and user_info.get("authenticated"):
        return {
            "authenticated": True,
            "username": user_info.get("username"),
            "user_id": user_info.get("user_id"),
            "email": user_info.get("email"),
            "roles": user_info.get("roles", []),
            "message": f"Авторизован как {user_info.get('username')}"
        }
    else:
        return {
            "authenticated": False,
            "message": "Не авторизован"
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
                "endpoints_test": results
            }
    except Exception as e:
        return {"error": str(e)}


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Главная страница системы"""
    user_info = getattr(request.state, 'user', None)

    if user_info and user_info.get("authenticated"):
        username = user_info.get("username", "Пользователь")
        auth_type = user_info.get("auth_type", "unknown")
    else:
        username = None
        auth_type = None

    return templates.TemplateResponse("home.html", {
        "request": request,
        "user_authenticated": user_info.get("authenticated", False) if user_info else False,
        "username": username,
        "auth_type": auth_type
    })


@app.get("/debug/form-test")
async def debug_form_test():
    return {"status": "ok", "message": "Form test endpoint works"}

@app.post("/debug/form-test")
async def debug_form_test_post(request: Request):
    try:
        data = await request.json()
        return {"status": "ok", "received": data, "message": "POST received"}
    except:
        return {"status": "error", "message": "No JSON data"}

if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 Starting server with SimpleSupersetAuthMiddleware")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_config=None,
        proxy_headers=True
    )
