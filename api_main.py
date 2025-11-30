# main.py
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from database.middleware import SupersetAuthMiddleware
from config import settings

# Импортируем роутеры
from api.students import router as students_router
from api.schedule import router as schedule_router
from api.trainers import router as trainers_router
from api.visits import router as visits_router
from api.competitions import router as competitions_router
from config import templates

app = FastAPI(title="Student Management System")

# Монтируем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")

# URL вашего Superset
SUPERSET_BASE_URL = settings.superset_conf.base_url

# Добавляем middleware ПРАВИЛЬНО (исправлено)
app.add_middleware(SupersetAuthMiddleware, superset_base_url=SUPERSET_BASE_URL)

# CORS (если нужно)
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
async def auth_callback(request: Request):
    """Callback endpoint для обработки редиректа после авторизации Superset"""
    # Получаем сессионную куку из запроса
    session_cookie = request.cookies.get("session")

    if session_cookie:
        # Перенаправляем пользователя на главную страницу
        response = RedirectResponse(url="/")
        response.set_cookie(key="session", value=session_cookie, httponly=True)
        return response

    # Если куки нет, возвращаем на логин
    return RedirectResponse(url=f"{SUPERSET_BASE_URL}/login/")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Главная страница системы"""
    # Middleware уже проверил аутентификацию
    return templates.TemplateResponse("home.html", {
        "request": request,
        "user_authenticated": True  # Если мы здесь, пользователь аутентифицирован
    })


@app.get("/logout")
async def logout():
    """Выход из системы"""
    response = RedirectResponse(url=f"{SUPERSET_BASE_URL}/logout/")
    response.delete_cookie("session")
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)