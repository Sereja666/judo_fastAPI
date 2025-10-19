# main.py
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker, Session
from typing import List, Optional
import json
import os
from datetime import datetime
from database.schemas import Students, Sport, Schedule, Students_schedule, Trainers, Prices, engine

# Создаем сессию базы данных
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI(title="Student Management System")

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

# ===== РАСПИСАНИЕ =====

@app.get("/")
async def root_redirect():
    """Редирект с корня на главную страницу расписания"""
    return RedirectResponse(url="/schedule/")

@app.get("/schedule/", response_class=HTMLResponse)
async def main_page(request: Request, db: Session = Depends(get_db)):
    """Главная страница с формой выбора ученика и расписания"""
    students = db.query(Students).filter(Students.active == True).all()
    sports = db.query(Sport).all()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "students": students,
        "sports": sports
    })

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

# ===== РЕДАКТИРОВАНИЕ УЧЕНИКОВ =====

@app.get("/edit-students", response_class=HTMLResponse)
async def edit_students_page(request: Request, db: Session = Depends(get_db)):
    """Главная страница редактирования учеников"""
    students = db.query(Students).filter(Students.active == True).all()
    sports = db.query(Sport).all()
    trainers = db.query(Trainers).all()
    prices = db.query(Prices).all()
    
    return templates.TemplateResponse("edit_students.html", {
        "request": request,
        "students": students,
        "sports": sports,
        "trainers": trainers,
        "prices": prices
    })

@app.get("/edit-students/search-students")
async def search_students_edit(query: str, db: Session = Depends(get_db)):
    """Поиск учеников по имени для автозаполнения на странице редактирования"""
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

@app.get("/edit-students/get-student-data/{student_id}")
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

@app.post("/edit-students/update-student")
async def update_student(
    student_id: int = Form(...),
    name: str = Form(...),
    birthday: Optional[str] = Form(None),
    sport_discipline: Optional[str] = Form(None),
    rang: Optional[str] = Form(None),
    sex: Optional[str] = Form(None),
    weight: Optional[str] = Form(None),
    reference1: Optional[str] = Form(None),
    reference2: Optional[str] = Form(None),
    reference3: Optional[str] = Form(None),
    head_trainer_id: Optional[str] = Form(None),
    second_trainer_id: Optional[str] = Form(None),
    price: Optional[str] = Form(None),
    payment_day: Optional[str] = Form(None),
    classes_remaining: Optional[str] = Form(None),
    expected_payment_date: Optional[str] = Form(None),
    telephone: Optional[str] = Form(None),
    parent1: Optional[str] = Form(None),
    parent2: Optional[str] = Form(None),
    date_start: Optional[str] = Form(None),
    telegram_id: Optional[str] = Form(None),
    active: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Обновление данных ученика"""
    try:
        print(f"Получены данные для student_id: {student_id}")
        
        student = db.query(Students).filter(Students.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Ученик не найден")
        
        # Функция для безопасного преобразования пустых строк в None
        def parse_value(value):
            if value is None or value == "":
                return None
            return value
        
        # Функция для преобразования в int или None
        def parse_int(value):
            if value is None or value == "":
                return None
            try:
                return int(value)
            except (ValueError, TypeError):
                return None

        # Функция для преобразования checkbox в boolean
        def parse_bool(value):
            return value == "on"
        
        # Обновляем поля
        student.name = name
        student.birthday = datetime.fromisoformat(birthday) if birthday else None
        student.sport_discipline = parse_int(sport_discipline)
        student.rang = parse_value(rang)
        student.sex = parse_value(sex)
        student.weight = parse_int(weight)
        student.reference1 = datetime.fromisoformat(reference1).date() if reference1 else None
        student.reference2 = datetime.fromisoformat(reference2).date() if reference2 else None
        student.reference3 = datetime.fromisoformat(reference3).date() if reference3 else None
        student.head_trainer_id = parse_int(head_trainer_id)
        student.second_trainer_id = parse_int(second_trainer_id)
        student.price = parse_int(price)
        student.payment_day = parse_int(payment_day)
        student.classes_remaining = parse_int(classes_remaining)
        student.expected_payment_date = datetime.fromisoformat(expected_payment_date).date() if expected_payment_date else None
        student.telephone = parse_value(telephone)
        student.parent1 = parse_int(parent1)
        student.parent2 = parse_int(parent2)
        student.date_start = datetime.fromisoformat(date_start) if date_start else None
        student.telegram_id = parse_int(telegram_id)
        student.active = parse_bool(active)  
        
        db.commit()
        
        return JSONResponse({"status": "success", "message": "Данные ученика успешно обновлены"})
    
    except Exception as e:
        db.rollback()
        print(f"Ошибка при сохранении: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка обновления: {str(e)}")

@app.post("/edit-students/create-student")
async def create_student(
    name: str = Form(...),
    birthday: Optional[str] = Form(None),
    sport_discipline: Optional[str] = Form(None),
    rang: Optional[str] = Form(None),
    sex: Optional[str] = Form(None),
    weight: Optional[str] = Form(None),
    reference1: Optional[str] = Form(None),
    reference2: Optional[str] = Form(None),
    reference3: Optional[str] = Form(None),
    head_trainer_id: Optional[str] = Form(None),
    second_trainer_id: Optional[str] = Form(None),
    price: Optional[str] = Form(None),
    payment_day: Optional[str] = Form(None),
    classes_remaining: Optional[str] = Form(None),
    expected_payment_date: Optional[str] = Form(None),
    telephone: Optional[str] = Form(None),
    parent1: Optional[str] = Form(None),
    parent2: Optional[str] = Form(None),
    date_start: Optional[str] = Form(None),
    telegram_id: Optional[str] = Form(None),
    active: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Создание нового ученика"""
    try:
        print("Создание нового ученика")
        
        # Функция для безопасного преобразования пустых строк в None
        def parse_value(value):
            if value is None or value == "":
                return None
            return value
        
        # Функция для преобразования в int или None
        def parse_int(value):
            if value is None or value == "":
                return None
            try:
                return int(value)
            except (ValueError, TypeError):
                return None

        # Функция для преобразования checkbox в boolean
        def parse_bool(value):
            return value == "on"

        # Создаем нового ученика
        new_student = Students(
            name=name,
            birthday=datetime.fromisoformat(birthday) if birthday else None,
            sport_discipline=parse_int(sport_discipline),
            rang=parse_value(rang),
            sex=parse_value(sex),
            weight=parse_int(weight),
            reference1=datetime.fromisoformat(reference1).date() if reference1 else None,
            reference2=datetime.fromisoformat(reference2).date() if reference2 else None,
            reference3=datetime.fromisoformat(reference3).date() if reference3 else None,
            head_trainer_id=parse_int(head_trainer_id),
            second_trainer_id=parse_int(second_trainer_id),
            price=parse_int(price),
            payment_day=parse_int(payment_day),
            classes_remaining=parse_int(classes_remaining),
            expected_payment_date=datetime.fromisoformat(expected_payment_date).date() if expected_payment_date else None,
            telephone=parse_value(telephone),
            parent1=parse_int(parent1),
            parent2=parse_int(parent2),
            date_start=datetime.fromisoformat(date_start) if date_start else None,
            telegram_id=parse_int(telegram_id),
            active=parse_bool(active) if active is not None else True
        )
        
        db.add(new_student)
        db.commit()
        db.refresh(new_student)
        
        print(f"Создан новый ученик с ID: {new_student.id}")
        
        return JSONResponse({
            "status": "success", 
            "message": "Ученик успешно создан",
            "student_id": new_student.id
        })
    
    except Exception as e:
        db.rollback()
        print(f"Ошибка при создании ученика: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка создания: {str(e)}")

@app.get("/edit-students/get-prices")
async def get_prices(db: Session = Depends(get_db)):
    """Получение списка всех цен"""
    prices = db.query(Prices).all()
    
    result = []
    for price in prices:
        result.append({
            "id": price.id,
            "price": price.price,
            "description": price.description or "",
            "classes_in_price": price.classes_in_price or 0
        })
    
    return JSONResponse(result)

# ===== СЛУЖЕБНЫЕ ЭНДПОИНТЫ =====

@app.get("/health")
async def health_check():
    """Эндпоинт для проверки здоровья приложения"""
    return {"status": "healthy", "service": "Student Management System"}

@app.get("/debug-auth")
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

@app.get("/logout")
async def logout():
    """Выход из системы - редирект на logout Superset"""
    response = RedirectResponse(url=f"{SUPERSET_BASE_URL}/logout/")
    # Очищаем cookie сессии
    response.delete_cookie("session")
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)