# main.py
from fastapi import FastAPI, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse  # ← Добавить импорт
from sqlalchemy.orm import Session
from starlette.responses import HTMLResponse

from database.middleware import SupersetAuthMiddleware
from config import settings
from config import templates

# Импортируем роутеры
from api.students import router as students_router
from api.schedule import router as schedule_router
from api.trainers import router as trainers_router
from api.visits import router as visits_router
from api.competitions import router as competitions_router
from database.schemas import Students, get_db, Sport

app = FastAPI(title="Student Management System")

# Монтируем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")

# URL вашего Superset
SUPERSET_BASE_URL = settings.superset_conf.base_url

# Добавляем middleware
# app.add_middleware(SupersetAuthMiddleware, superset_base_url=SUPERSET_BASE_URL)

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

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    """Главная страница расписания"""
    students = db.query(Students).filter(Students.active == True).all()
    sports = db.query(Sport).all()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "students": students,
        "sports": sports
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)