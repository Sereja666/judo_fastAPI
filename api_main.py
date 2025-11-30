# main.py
import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import httpx

# Импортируем middleware
from database.middleware import StrictSupersetAuthMiddleware
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

# Trusted Hosts middleware для правильных URL (ДОЛЖЕН БЫТЬ ПЕРВЫМ)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["api.srm-1legion.ru", "localhost", "127.0.0.1"])

# Монтируем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")

# URL вашего Superset
SUPERSET_BASE_URL = settings.superset_conf.base_url

# Middleware аутентификации (ВАЖНО: после TrustedHostMiddleware)
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
        # Используем HTTPS URL для редиректа
        safe_return_url = return_url.replace('http://', 'https://')

        # Проверяем, что сессия действительно валидна
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{SUPERSET_BASE_URL}/api/v1/security/current",
                    cookies={"session": session_cookie},
                    timeout=10.0
                )
                if response.status_code == 200:
                    response = RedirectResponse(url=safe_return_url)
                    response.set_cookie(
                        key="session",
                        value=session_cookie,
                        httponly=True,
                        secure=True,  # Важно для HTTPS!
                        max_age=24 * 60 * 60,
                        samesite="lax"
                    )
                    logger.info("✅ Успешная аутентификация через callback")
                    return response
                else:
                    logger.warning(f"⚠️ Невалидная сессия в callback: статус {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Ошибка проверки сессии в callback: {e}")

    # Если что-то пошло не так - снова на логин
    logger.warning("⚠️ Неудачная аутентификация в callback")
    safe_login_url = f"{SUPERSET_BASE_URL}/login/"
    return RedirectResponse(url=safe_login_url)


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
        "cookies": dict(request.cookies),
        "base_url": str(request.base_url),
        "url": str(request.url)
    }


@app.get("/debug/request-info")
async def debug_request_info(request: Request):
    """Информация о запросе"""
    return {
        "method": request.method,
        "url": str(request.url),
        "base_url": str(request.base_url),
        "headers": dict(request.headers),
        "cookies": dict(request.cookies),
        "client": request.client,
        "scheme": request.url.scheme
    }


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Главная страница системы"""
    # Если пользователь здесь - он уже прошел аутентификацию
    return templates.TemplateResponse("home.html", {
        "request": request,
        "user_authenticated": True
    })


if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 Starting server with STRICT Superset authentication")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_config=None,
        proxy_headers=True,  # Важно для работы за reverse proxy
        forwarded_allow_ips="*"  # Разрешаем forwarded headers
    )