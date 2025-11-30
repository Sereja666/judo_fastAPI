# main.py
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from database.middleware import SupersetAuthMiddleware
from config import settings
import httpx
import json

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

# Добавляем middleware
app.add_middleware(SupersetAuthMiddleware, superset_base_url=SUPERSET_BASE_URL)

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
    # Получаем сессионную куку из запроса
    session_cookie = request.cookies.get("session")

    logger.info(f"🔹 Callback получен, return_url: {return_url}")
    logger.info(f"🔹 Сессионная кука в callback: {'есть' if session_cookie else 'нет'}")

    if session_cookie:
        # Перенаправляем пользователя на запрошенную страницу
        response = RedirectResponse(url=return_url)
        response.set_cookie(
            key="session",
            value=session_cookie,
            httponly=True,
            max_age=24 * 60 * 60,  # 24 часа
            samesite="lax"
        )
        logger.info("✅ Сессия установлена, редирект на целевую страницу")
        return response

    # Если куки нет, возвращаем на логин
    logger.warning("⚠️ В callback не получена сессионная кука")
    return RedirectResponse(url=f"{SUPERSET_BASE_URL}/login/")


@app.get("/logout")
async def logout():
    """Выход из системы"""
    response = RedirectResponse(url=f"{SUPERSET_BASE_URL}/logout/")
    response.delete_cookie("session")
    return response


@app.get("/debug/cookies")
async def debug_cookies(request: Request):
    """Эндпоинт для отладки кук"""
    cookies = dict(request.cookies)
    return JSONResponse({
        "cookies": cookies,
        "session_cookie_present": "session" in cookies,
        "session_cookie_length": len(cookies.get("session", "")),
        "session_cookie_preview": cookies.get("session", "")[:50] + "..." if cookies.get("session") else None,
        "headers": {k: v for k, v in request.headers.items() if k.lower() not in ['authorization', 'cookie']}
    })


@app.get("/debug/superset-check")
async def debug_superset_check(request: Request):
    """Эндпоинт для проверки подключения к Superset"""
    session_cookie = request.cookies.get("session")

    if not session_cookie:
        return JSONResponse({"error": "No session cookie"}, status=400)

    try:
        async with httpx.AsyncClient() as client:
            cookies = {"session": session_cookie}
            headers = {
                "User-Agent": "StudentManagementSystem/1.0",
                "Accept": "application/json",
            }

            check_url = f"{SUPERSET_BASE_URL}/api/v1/security/current"
            response = await client.get(
                check_url,
                cookies=cookies,
                headers=headers,
                timeout=10.0,
                follow_redirects=False
            )

            return JSONResponse({
                "superset_url": SUPERSET_BASE_URL,
                "check_url": check_url,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "response_preview": response.text[:500] if response.text else None,
                "session_cookie_length": len(session_cookie),
                "session_cookie_preview": session_cookie[:50] + "..."
            })

    except Exception as e:
        return JSONResponse({
            "error": str(e),
            "superset_url": SUPERSET_BASE_URL,
            "type": type(e).__name__
        }, status=500)


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Главная страница системы"""
    return templates.TemplateResponse("home.html", {
        "request": request,
        "user_authenticated": True
    })


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)