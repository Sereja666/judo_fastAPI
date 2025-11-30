# main.py
import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

# Импортируем оба middleware
from database.middleware import SupersetAuthMiddleware, DevelopmentAuthMiddleware
from config import settings

# Импортируем роутеры
from api.students import router as students_router
from api.schedule import router as schedule_router
from api.trainers import router as trainers_router
from api.visits import router as visits_router
from api.competitions import router as competitions_router
from config import templates
from logger_config import logger

app = FastAPI(title="Student Management System")

# Монтируем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")

# URL вашего Superset
SUPERSET_BASE_URL = settings.superset_conf.base_url


# УМНОЕ ПОДКЛЮЧЕНИЕ MIDDLEWARE
def setup_middleware():
    """Настраивает middleware в зависимости от окружения"""

    # Проверяем доступность Superset в фоновом режиме
    async def check_superset_availability():
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{SUPERSET_BASE_URL}/api/v1/security/current",
                    timeout=5.0
                )
                return response.status_code == 200
        except:
            return False

    # Определяем режим работы
    environment = os.getenv("ENVIRONMENT", "development")
    superset_available = False

    # В продакшн режиме всегда используем Superset auth
    if environment == "production":
        logger.info("🚀 PRODUCTION MODE: Подключаем Superset аутентификацию")
        app.add_middleware(SupersetAuthMiddleware, superset_base_url=SUPERSET_BASE_URL)
        return

    # В разработке проверяем доступность Superset
    import asyncio
    try:
        # Запускаем проверку
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Если loop уже запущен, запускаем в отдельной task
            asyncio.create_task(check_superset_availability())
            superset_available = False  # По умолчанию false для безопасности
        else:
            superset_available = asyncio.run(check_superset_availability())
    except:
        superset_available = False

    if superset_available:
        logger.info("✅ Superset доступен, подключаем аутентификацию")
        app.add_middleware(SupersetAuthMiddleware, superset_base_url=SUPERSET_BASE_URL)
    else:
        logger.warning("⚠️ Superset недоступен, используем DEV режим")
        app.add_middleware(DevelopmentAuthMiddleware, superset_base_url=SUPERSET_BASE_URL)


# Подключаем middleware
setup_middleware()

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
    return {
        "status": "healthy",
        "service": "Student Management System",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "superset_available": False  # Можно улучшить эту проверку
    }


@app.get("/auth/callback")
async def auth_callback(request: Request, return_url: str = "/"):
    """Callback endpoint для обработки редиректа после авторизации Superset"""
    session_cookie = request.cookies.get("session")

    if session_cookie:
        response = RedirectResponse(url=return_url)
        response.set_cookie(
            key="session",
            value=session_cookie,
            httponly=True,
            max_age=24 * 60 * 60
        )
        return response

    return RedirectResponse(url=f"{SUPERSET_BASE_URL}/login/")


@app.get("/debug/middleware-info")
async def debug_middleware_info():
    """Информация о текущем режиме middleware"""
    return {
        "environment": os.getenv("ENVIRONMENT", "development"),
        "superset_url": SUPERSET_BASE_URL,
        "middleware_mode": "development" if any(
            isinstance(m, DevelopmentAuthMiddleware) for m in app.user_middleware) else "superset"
    }


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Главная страница системы"""
    user = getattr(request.state, 'user', None)
    return templates.TemplateResponse("home.html", {
        "request": request,
        "user_authenticated": True,
        "user": user,
        "environment": os.getenv("ENVIRONMENT", "development")
    })


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)