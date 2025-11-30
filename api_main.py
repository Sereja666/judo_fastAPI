# main.py
import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import httpx

# Импортируем ТОЛЬКО Superset middleware
from database.middleware import StrictSupersetAuthMiddleware
from config import settings
from config import templates
from logger_config import logger

# Импортируем роутеры
from api.students import router as students_router
from api.schedule import router as schedule_router
from api.trainers import router as trainers_router
from api.visits import router as visits_router
from api.competitions import router as competitions_router

app = FastAPI(title="Student Management System")

# Монтируем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")

# URL вашего Superset
SUPERSET_BASE_URL = settings.superset_conf.base_url

# ВСЕГДА используем Strict Superset auth
app.add_middleware(StrictSupersetAuthMiddleware, superset_base_url=SUPERSET_BASE_URL)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{SUPERSET_BASE_URL}/api/v1/security/current",
                    cookies={"session": session_cookie},
                    timeout=10.0
                )
                if response.status_code == 200:
                    response = RedirectResponse(url=return_url)
                    response.set_cookie(
                        key="session",
                        value=session_cookie,
                        httponly=True,
                        max_age=24 * 60 * 60
                    )
                    logger.info("✅ Успешная аутентификация через callback")
                    return response
        except Exception as e:
            logger.error(f"❌ Ошибка проверки сессии в callback: {e}")

    # Если что-то пошло не так - снова на логин
    logger.warning("⚠️ Неудачная аутентификация в callback")
    return RedirectResponse(url=f"{SUPERSET_BASE_URL}/login/")


@app.get("/logout")
async def logout():
    """Выход из системы"""
    response = RedirectResponse(url=f"{SUPERSET_BASE_URL}/logout/")
    response.delete_cookie("session")
    return response


@app.get("/debug/superset-status")
async def debug_superset_status():
    """Проверка статуса Superset"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(SUPERSET_BASE_URL, timeout=5.0)
            return {
                "superset_url": SUPERSET_BASE_URL,
                "status": "available",
                "status_code": response.status_code,
                "response_time": f"{response.elapsed.total_seconds():.2f}s"
            }
    except Exception as e:
        return {
            "superset_url": SUPERSET_BASE_URL,
            "status": "unavailable",
            "error": str(e)
        }


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Главная страница системы"""
    # Если пользователь здесь - он уже прошел аутентификацию
    return templates.TemplateResponse("home.html", {
        "request": request,
        "user_authenticated": True
    })


@app.get("/debug/middleware-check")
async def debug_middleware_check(request: Request):
    """Проверка подключенных middleware"""
    middleware_info = []
    for i, middleware in enumerate(app.user_middleware):
        middleware_info.append({
            "position": i,
            "cls": str(middleware.cls),
            "options": middleware.options
        })

    return {
        "total_middleware": len(app.user_middleware),
        "middleware_list": middleware_info,
        "request_path": request.url.path,
        "cookies": dict(request.cookies)
    }


if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 Starting server with STRICT Superset authentication")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)