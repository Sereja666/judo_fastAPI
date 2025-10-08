# main.py
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker, Session
from typing import List, Optional
import json
import os

from database.schemas import Students, Sport, Schedule, Students_schedule, engine

# Создаем сессию базы данных
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI(title="Student Schedule Manager")

# URL вашего Superset
SUPERSET_BASE_URL = "http://185.35.192.169/superset"

# Создаем папку templates если её нет
if not os.path.exists("templates"):
    os.makedirs("templates")

templates = Jinja2Templates(directory="templates")

# Middleware для проверки аутентификации Superset
@app.middleware("http")
async def check_superset_auth(request: Request, call_next):
    """
    Простая проверка аутентификации:
    Проверяем наличие сессионной cookie от Superset
    """

    # Пропускаем статические файлы и health checks
    if request.url.path.startswith("/static/") or request.url.path == "/health":
        return await call_next(request)

    # Проверяем наличие сессионной cookie с именем 'session'
    session_cookie = request.cookies.get("session")

    if not session_cookie:
        # Если cookie нет - редирект на страницу логина Superset
        print("❌ Сессионная cookie не найдена, редирект на логин Superset")
        return RedirectResponse(url=f"{SUPERSET_BASE_URL}/login/")

    # Если cookie есть - пропускаем запрос дальше
    print("✅ Сессионная cookie найдена, доступ разрешен")
    return await call_next(request)

# Зависимость для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
async def root_redirect():
    """Редирект с корня на главную страницу расписания"""
    return RedirectResponse(url="/schedule/")
    
# ГЛАВНАЯ СТРАНИЦА С ПРЕФИКСОМ /schedule
@app.get("/schedule/", response_class=HTMLResponse)
async def main_page(request: Request, db: Session = Depends(get_db)):
    """Главная страница с формой выбора ученика и расписания"""
    # Получаем всех активных учеников
    students = db.query(Students).filter(Students.active == True).all()
    sports = db.query(Sport).all()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "students": students,
        "sports": sports
    })

# ВСЕ остальные эндпоинты тоже с префиксом /schedule
@app.get("/schedule/search-students")
async def search_students(query: str, db: Session = Depends(get_db)):
    """Поиск учеников по имени для автозаполнения"""
    if not query or len(query) < 2:
        return JSONResponse([])

    students = db.query(Students).filter(
        and_(
            Students.active == True,
            Students.name.ilike(f"%{query}%")
        )
    ).limit(10).all()

    result = [{"id": student.id, "name": student.name} for student in students]
    return JSONResponse(result)

@app.get("/schedule/get-schedules")
async def get_schedules(sport_id: int, db: Session = Depends(get_db)):
    """Получение расписания по выбранной дисциплине с сортировкой только по описанию"""
    schedules = db.query(Schedule).filter(Schedule.sport_discipline == sport_id).all()

    # Сортируем расписание только по описанию
    sorted_schedules = sorted(schedules, key=lambda x: x.description or "")

    result = []
    for schedule in sorted_schedules:
        result.append({
            "id": schedule.id,
            "day_week": schedule.day_week,
            "time_start": str(schedule.time_start),
            "time_end": str(schedule.time_end),
            "description": schedule.description or ""
        })

    return JSONResponse(result)

@app.get("/schedule/get-student-schedules")
async def get_student_schedules(student_id: int, db: Session = Depends(get_db)):
    """Получение текущего расписания ученика"""
    student_schedules = db.query(Students_schedule).filter(
        Students_schedule.student == student_id
    ).all()

    result = [ss.schedule for ss in student_schedules]
    return JSONResponse(result)

@app.post("/schedule/save-schedule")
async def save_schedule(
        student_id: int = Form(...),
        sport_id: int = Form(...),
        schedule_ids: List[int] = Form(...),
        db: Session = Depends(get_db)
):
    """Сохранение расписания ученика"""
    try:
        # Удаляем существующее расписание для этого ученика
        db.query(Students_schedule).filter(
            Students_schedule.student == student_id
        ).delete()

        # Добавляем новое расписание
        for schedule_id in schedule_ids:
            student_schedule = Students_schedule(
                student=student_id,
                schedule=schedule_id
            )
            db.add(student_schedule)

        db.commit()

        return JSONResponse({"status": "success", "message": "Расписание успешно сохранено"})

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения: {str(e)}")

@app.get("/schedule/student-schedule/{student_id}", response_class=HTMLResponse)
async def student_schedule_page(request: Request, student_id: int, db: Session = Depends(get_db)):
    """Страница управления расписанием конкретного ученика"""
    student = db.query(Students).filter(Students.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Ученик не найден")

    sports = db.query(Sport).all()

    return templates.TemplateResponse("student_schedule.html", {
        "request": request,
        "student": student,
        "sports": sports
    })

@app.get("/schedule/health")
async def health_check():
    """Эндпоинт для проверки здоровья приложения"""
    return {"status": "healthy", "service": "Student Schedule Manager"}

@app.get("/schedule/debug-auth")
async def debug_auth(request: Request):
    """Эндпоинт для отладки аутентификации"""
    cookies = dict(request.cookies)
    session_cookie = request.cookies.get("session")

    return {
        "session_cookie_present": bool(session_cookie),
        "session_cookie_length": len(session_cookie) if session_cookie else 0,
        "all_cookies": list(cookies.keys()),
        "superset_login_url": f"{SUPERSET_BASE_URL}/login/"
    }

@app.get("/schedule/logout")
async def logout():
    """Выход из системы - редирект на logout Superset"""
    response = RedirectResponse(url=f"{SUPERSET_BASE_URL}/logout/")
    # Очищаем cookie сессии
    response.delete_cookie("session")
    return response

# Добавьте эти импорты в начало файла
from datetime import datetime
from database.schemas import Trainers


# Добавьте эти маршруты в основной файл после существующих маршрутов:

@app.get("/edit-students", response_class=HTMLResponse)
async def edit_students_page(request: Request, db: Session = Depends(get_db)):
    """Главная страница редактирования учеников"""
    students = db.query(Students).filter(Students.active == True).all()
    sports = db.query(Sport).all()
    trainers = db.query(Trainers).all()

    return templates.TemplateResponse("edit_students.html", {
        "request": request,
        "students": students,
        "sports": sports,
        "trainers": trainers
    })


@app.get("/get-student-data/{student_id}")
async def get_student_data(student_id: int, db: Session = Depends(get_db)):
    """Получение полных данных ученика"""
    student = db.query(Students).filter(Students.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Ученик не найден")

    # Преобразуем данные для JSON
    student_data = {
        "id": student.id,
        "name": student.name,
        "birthday": student.birthday.isoformat() if student.birthday else None,
        "sport_discipline": student.sport_discipline,
        "rang": student.rang or "",
        "sex": student.sex or "",
        "weight": student.weight,
        "reference1": student.reference1.isoformat() if student.reference1 else None,
        "reference2": student.reference2.isoformat() if student.reference2 else None,
        "reference3": student.reference3.isoformat() if student.reference3 else None,
        "head_trainer_id": student.head_trainer_id,
        "second_trainer_id": student.second_trainer_id,
        "price": student.price,
        "payment_day": student.payment_day,
        "classes_remaining": student.classes_remaining,
        "expected_payment_date": student.expected_payment_date.isoformat() if student.expected_payment_date else None,
        "telephone": student.telephone or "",
        "parent1": student.parent1,
        "parent2": student.parent2,
        "date_start": student.date_start.isoformat() if student.date_start else None,
        "telegram_id": student.telegram_id,
        "active": student.active
    }

    return JSONResponse(student_data)


@app.post("/update-student")
async def update_student(
        student_id: int = Form(...),
        name: str = Form(...),
        birthday: str = Form(None),
        sport_discipline: int = Form(None),
        rang: str = Form(None),
        sex: str = Form(None),
        weight: int = Form(None),
        reference1: str = Form(None),
        reference2: str = Form(None),
        reference3: str = Form(None),
        head_trainer_id: int = Form(None),
        second_trainer_id: int = Form(None),
        price: int = Form(None),
        payment_day: int = Form(None),
        classes_remaining: int = Form(None),
        expected_payment_date: str = Form(None),
        telephone: str = Form(None),
        parent1: int = Form(None),
        parent2: int = Form(None),
        date_start: str = Form(None),
        telegram_id: int = Form(None),
        db: Session = Depends(get_db)
):
    """Обновление данных ученика"""
    try:
        student = db.query(Students).filter(Students.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Ученик не найден")

        # Обновляем поля
        student.name = name
        student.birthday = datetime.fromisoformat(birthday) if birthday else None
        student.sport_discipline = sport_discipline
        student.rang = rang
        student.sex = sex
        student.weight = weight
        student.reference1 = datetime.fromisoformat(reference1).date() if reference1 else None
        student.reference2 = datetime.fromisoformat(reference2).date() if reference2 else None
        student.reference3 = datetime.fromisoformat(reference3).date() if reference3 else None
        student.head_trainer_id = head_trainer_id
        student.second_trainer_id = second_trainer_id
        student.price = price
        student.payment_day = payment_day
        student.classes_remaining = classes_remaining
        student.expected_payment_date = datetime.fromisoformat(
            expected_payment_date).date() if expected_payment_date else None
        student.telephone = telephone
        student.parent1 = parent1
        student.parent2 = parent2
        student.date_start = datetime.fromisoformat(date_start) if date_start else None
        student.telegram_id = telegram_id

        db.commit()

        return JSONResponse({"status": "success", "message": "Данные ученика успешно обновлены"})

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка обновления: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)