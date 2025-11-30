# main.py
import base64
import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import httpx

# Импортируем middleware
from database.middleware import  StrictRedirectBasedAuthMiddleware
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

# Middleware аутентификации (ПЕРВЫМ!)
# app.add_middleware(StrictRedirectBasedAuthMiddleware, superset_base_url=SUPERSET_BASE_URL)

# # CORS
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

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


@app.get("/debug/cookie-analysis")
async def debug_cookie_analysis(request: Request):
    """Анализ куки сессии"""
    session_cookie = request.cookies.get("session")

    if not session_cookie:
        return {"error": "No session cookie"}

    analysis = {
        "cookie_present": True,
        "cookie_length": len(session_cookie),
        "cookie_preview": session_cookie[:100] + "..." if len(session_cookie) > 100 else session_cookie,
        "estimated_status": "guest" if len(session_cookie) < 200 else "possibly_authenticated"
    }

    # Проверяем через middleware
    from database.middleware import StrictRedirectBasedAuthMiddleware
    checker = StrictRedirectBasedAuthMiddleware(app=None, superset_base_url=SUPERSET_BASE_URL)

    analysis["api_check"] = await checker._check_api_access(session_cookie)
    analysis["main_page_check"] = await checker._check_main_page(session_cookie)
    analysis["profile_check"] = await checker._check_user_profile(session_cookie)
    analysis["final_decision"] = await checker._strict_authentication_check(session_cookie)

    return analysis
#
# @app.get("/", response_class=HTMLResponse)
# async def root(request: Request):
#     """Главная страница системы"""
#     # Если пользователь здесь - он уже прошел аутентификацию
#     return templates.TemplateResponse("home.html", {
#         "request": request,
#         "user_authenticated": True
#     })


# api_main.py - добавьте эти эндпоинты

@app.get("/debug/user-info")
async def debug_user_info(request: Request):
    """Информация о текущем пользователе"""
    user_info = getattr(request.state, 'user', None)

    if user_info and user_info.get("authenticated"):
        return {
            "authenticated": True,
            "username": user_info.get("username"),
            "user_id": user_info.get("user_id"),
            "roles": user_info.get("roles", []),
            "message": f"Добро пожаловать, {user_info.get('username')}!"
        }
    else:
        return {
            "authenticated": False,
            "message": "Пользователь не авторизован"
        }


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Главная страница системы"""
    user_info = getattr(request.state, 'user', None)
    username = user_info.get("username", "Гость") if user_info and user_info.get("authenticated") else "Гость"

    return templates.TemplateResponse("home.html", {
        "request": request,
        "user_authenticated": user_info.get("authenticated", False) if user_info else False,
        "username": username
    })


# В других роутерах вы тоже можете использовать request.state.user
@app.get("/profile")
async def user_profile(request: Request):
    """Профиль пользователя"""
    user_info = getattr(request.state, 'user', None)

    if not user_info or not user_info.get("authenticated"):
        return RedirectResponse(url="/")

    return {
        "username": user_info.get("username"),
        "user_id": user_info.get("user_id"),
        "roles": user_info.get("roles", [])
    }


# api_main.py
@app.get("/debug/cookie-decode")
async def debug_cookie_decode(request: Request):
    """Попытка декодировать куку сессии"""
    session_cookie = request.cookies.get("session")

    if not session_cookie:
        return {"error": "No session cookie"}

    analysis = {
        "cookie_length": len(session_cookie),
        "cookie_preview": session_cookie[:100] + "..." if len(session_cookie) > 100 else session_cookie,
    }

    # Пробуем декодировать как base64
    try:
        # Убираем возможные префиксы
        cookie_data = session_cookie
        if '.' in session_cookie:
            parts = session_cookie.split('.')
            for part in parts:
                try:
                    decoded = base64.b64decode(part + '=' * (-len(part) % 4))
                    analysis["base64_decoded"] = decoded.decode('utf-8', errors='ignore')
                    break
                except:
                    continue
    except Exception as e:
        analysis["decode_error"] = str(e)

    # Проверяем через middleware
    from database.middleware import StrictRedirectBasedAuthMiddleware
    checker = StrictRedirectBasedAuthMiddleware(app=None, superset_base_url=SUPERSET_BASE_URL)

    user_info = await checker._get_user_info(session_cookie)
    analysis["user_info"] = user_info

    return analysis


if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 Starting server with RedirectBasedAuthMiddleware")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_config=None,
        proxy_headers=True,  # Важно для работы за reverse proxy
        forwarded_allow_ips="*"  # Разрешаем forwarded headers
    )