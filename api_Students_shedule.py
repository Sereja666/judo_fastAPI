# main.py
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker, Session
from typing import List, Optional
import json
import os
from datetime import datetime, timedelta
from database.middleware import SupersetAuthMiddleware
from config import settings
from database.schemas import Students, Sport, Schedule, Students_schedule, Trainers, Prices, engine, Visits, \
    Training_place, Сompetition
from logger_config import logger



# Создаем сессию базы данных
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI(title="Student Management System")

# URL вашего Superset
SUPERSET_BASE_URL = settings.superset_conf.base_url

# app.add_middleware(SupersetAuthMiddleware, superset_base_url=SUPERSET_BASE_URL)

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

# ===== РЕДАКТИРОВАНИЕ ТРЕНЕРОВ =====

# Оставьте только эти endpoints для тренеров:

@app.get("/edit-trainers", response_class=HTMLResponse)
async def edit_trainers_page(request: Request, db: Session = Depends(get_db)):
    """Главная страница редактирования тренеров"""
    trainers = db.query(Trainers).filter(Trainers.active == True).all()
    sports = db.query(Sport).all()
    
    return templates.TemplateResponse("edit_trainers.html", {
        "request": request,
        "trainers": trainers,
        "sports": sports
    })

@app.get("/get-trainer-data/{trainer_id}")
async def get_trainer_data(trainer_id: int, db: Session = Depends(get_db)):
    """Получение данных тренера - полная версия"""
    try:
        print(f"🔹 Запрос тренера ID: {trainer_id}")
        
        trainer = db.query(Trainers).filter(Trainers.id == trainer_id).first()
        if not trainer:
            return JSONResponse({"error": "Тренер не найден"}, status_code=404)

        # Полный набор полей из таблицы Trainers
        response_data = {
            "id": trainer.id,
            "name": trainer.name or "",
            "telephone": trainer.telephone or "",
            "telegram_id": trainer.telegram_id,
            "sport_discipline": trainer.sport_discipline,
            "sex": trainer.sex or "",
            "birthday": trainer.birthday.isoformat() if trainer.birthday else None,
            "active": trainer.active
        }
        
        print(f"✅ Отправляем полные данные тренера: {response_data}")
        return JSONResponse(response_data)
        
    except Exception as e:
        print(f"❌ Ошибка: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/update-trainer")
async def update_trainer(
    trainer_id: int = Form(...),
    name: str = Form(...),
    birthday: Optional[str] = Form(None),
    sport_discipline: Optional[str] = Form(None),
    sex: Optional[str] = Form(None),
    telephone: Optional[str] = Form(None),
    telegram_id: Optional[str] = Form(None),
    active: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Обновление данных тренера"""
    try:
        print(f"Обновление тренера ID: {trainer_id}")
        
        # Вспомогательные функции для обработки данных
        def parse_value(value):
            if value is None or value == "":
                return None
            return value
        
        def parse_int(value):
            if value is None or value == "":
                return None
            try:
                return int(value)
            except (ValueError, TypeError):
                return None

        def parse_bool(value):
            return value == "on"
        
        trainer = db.query(Trainers).filter(Trainers.id == trainer_id).first()
        if not trainer:
            raise HTTPException(status_code=404, detail="Тренер не найден")
        
        # Обновляем все поля
        trainer.name = name
        trainer.birthday = datetime.fromisoformat(birthday) if birthday else None
        trainer.sport_discipline = parse_int(sport_discipline)
        trainer.sex = parse_value(sex)
        trainer.telephone = parse_value(telephone)
        trainer.telegram_id = parse_int(telegram_id)
        trainer.active = parse_bool(active)
        
        db.commit()
        
        print(f"Тренер {trainer_id} успешно обновлен")
        return JSONResponse({"status": "success", "message": "Данные тренера успешно обновлены"})
    
    except Exception as e:
        db.rollback()
        print(f"Ошибка при обновлении тренера: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка обновления: {str(e)}")

# ===== СЛУЖЕБНЫЕ ЭНДПОИНТЫ =====
@app.get("/debug-trainers")
async def debug_trainers(db: Session = Depends(get_db)):
    """Отладочный endpoint для проверки тренеров в БД"""
    trainers = db.query(Trainers).all()
    
    result = []
    for trainer in trainers:
        result.append({
            "id": trainer.id,
            "name": trainer.name,
            "active": trainer.active
        })
    
    return JSONResponse(result)

@app.get("/debug-trainer-structure")
async def debug_trainer_structure(db: Session = Depends(get_db)):
    """Отладочный endpoint для проверки структуры таблицы тренеров"""
    # Получим первого тренера чтобы увидеть все поля
    trainer = db.query(Trainers).first()
    
    if not trainer:
        return JSONResponse({"error": "Нет тренеров в базе данных"})
    
    # Получим все атрибуты тренера
    result = {}
    for column in Trainers.__table__.columns:
        column_name = column.name
        column_value = getattr(trainer, column_name)
        result[column_name] = {
            "value": str(column_value) if column_value is not None else None,
            "type": str(type(column_value))
        }
    
    return JSONResponse(result)

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

@app.get("/debug-routes")
async def debug_routes():
    """Отладочный endpoint для просмотра всех зарегистрированных маршрутов"""
    routes = []
    for route in app.routes:
        route_info = {
            "path": getattr(route, "path", None),
            "methods": getattr(route, "methods", None),
            "name": getattr(route, "name", None)
        }
        routes.append(route_info)
    return JSONResponse(routes)

@app.get("/logout")
async def logout():
    """Выход из системы - редирект на logout Superset"""
    response = RedirectResponse(url=f"{SUPERSET_BASE_URL}/logout/")
    # Очищаем cookie сессии
    response.delete_cookie("session")
    return response


# ===== УПРАВЛЕНИЕ ПОСЕЩЕНИЯМИ =====

@app.get("/visits/", response_class=HTMLResponse)
async def visits_page(request: Request, db: Session = Depends(get_db)):
    """Главная страница управления посещениями"""
    try:
        trainers = db.query(Trainers).filter(Trainers.active == True).all()
        sports = db.query(Sport).all()
        training_places = db.query(Training_place).all()

        return templates.TemplateResponse("visits.html", {
            "request": request,
            "trainers": trainers,
            "sports": sports,
            "training_places": training_places
        })
    except Exception as e:
        print(f"Error in visits_page: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/visits/get-schedules-by-date")
async def get_schedules_by_date(date: str, db: Session = Depends(get_db)):
    """Получение расписания на конкретную дату"""
    try:
        print(f"Getting schedules for date: {date}")
        selected_date = datetime.fromisoformat(date).date()
        day_of_week = selected_date.strftime('%A').lower()

        # Маппинг английских названий дней недели на русские
        day_mapping = {
            'monday': 'понедельник',
            'tuesday': 'вторник',
            'wednesday': 'среда',
            'thursday': 'четверг',
            'friday': 'пятница',
            'saturday': 'суббота',
            'sunday': 'воскресенье'
        }

        russian_day = day_mapping.get(day_of_week, day_of_week)
        print(f"Russian day: {russian_day}")

        # Получаем расписание на этот день недели
        schedules = db.query(Schedule).filter(
            Schedule.day_week == russian_day
        ).all()

        print(f"Found {len(schedules)} schedules")

        result = []
        for schedule in schedules:
            # Получаем информацию о месте тренировки
            place = db.query(Training_place).filter(Training_place.id == schedule.training_place).first()
            sport = db.query(Sport).filter(Sport.id == schedule.sport_discipline).first()

            result.append({
                "id": schedule.id,
                "time_start": str(schedule.time_start),
                "time_end": str(schedule.time_end),
                "place_name": place.name if place else "Неизвестно",
                "sport_name": sport.name if sport else "Неизвестно",
                "description": schedule.description or "",
                "training_place": schedule.training_place,
                "sport_discipline": schedule.sport_discipline
            })

        return JSONResponse(result)

    except Exception as e:
        print(f"Error in get_schedules_by_date: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения расписания: {str(e)}")


@app.get("/visits/get-students-by-schedule")
async def get_students_by_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Получение студентов, записанных на конкретное расписание"""
    try:
        print(f"Getting students for schedule: {schedule_id}")

        # Получаем студентов из расписания
        student_schedules = db.query(Students_schedule).filter(
            Students_schedule.schedule == schedule_id
        ).all()

        print(f"Found {len(student_schedules)} student schedule records")

        students = []
        for ss in student_schedules:
            student = db.query(Students).filter(
                and_(
                    Students.id == ss.student,
                    Students.active == True
                )
            ).first()

            if student:
                students.append({
                    "id": student.id,
                    "name": student.name,
                    "rang": student.rang or "",
                    "weight": student.weight or 0
                })

        print(f"Returning {len(students)} students")
        return JSONResponse(students)

    except Exception as e:
        print(f"Error in get_students_by_schedule: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения студентов: {str(e)}")


@app.get("/visits/search-students")
async def search_students_visits(query: str, db: Session = Depends(get_db)):
    """Поиск студентов для добавления не по расписанию"""
    try:
        print(f"Searching students with query: {query}")

        if not query or len(query) < 2:
            return JSONResponse([])

        students = db.query(Students).filter(
            and_(
                Students.active == True,
                Students.name.ilike(f"%{query}%")
            )
        ).limit(10).all()

        result = [{"id": student.id, "name": student.name} for student in students]
        print(f"Found {len(result)} students")
        return JSONResponse(result)

    except Exception as e:
        print(f"Error in search_students_visits: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка поиска студентов: {str(e)}")


@app.post("/visits/save-visits")
async def save_visits(
        visit_date: str = Form(...),
        schedule_id: int = Form(...),
        trainer_id: int = Form(...),
        student_ids: List[int] = Form([]),
        extra_student_ids: List[int] = Form([]),
        db: Session = Depends(get_db)
):
    """Сохранение посещений"""
    try:
        print(f"Saving visits - date: {visit_date}, schedule: {schedule_id}, trainer: {trainer_id}")
        print(f"Students: {student_ids}, Extra: {extra_student_ids}")

        visit_datetime = datetime.fromisoformat(visit_date)

        # Получаем информацию о расписании
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule:
            raise HTTPException(status_code=404, detail="Расписание не найдено")

        success_count = 0
        error_messages = []

        # Обрабатываем студентов из расписания
        for student_id in student_ids:
            try:
                # Проверяем, не было ли уже посещения сегодня
                existing_visit = db.query(Visits).filter(
                    and_(
                        Visits.student == student_id,
                        Visits.shedule == schedule_id,
                        Visits.data >= visit_datetime.replace(hour=0, minute=0, second=0),
                        Visits.data < visit_datetime.replace(hour=23, minute=59, second=59)
                    )
                ).first()

                if existing_visit:
                    error_messages.append(f"Студент ID {student_id} уже отмечен сегодня")
                    continue

                # Создаем запись о посещении
                visit = Visits(
                    data=visit_datetime,
                    trainer=trainer_id,
                    student=student_id,
                    place=schedule.training_place,
                    sport_discipline=schedule.sport_discipline,
                    shedule=schedule_id
                )

                db.add(visit)
                success_count += 1

            except Exception as e:
                error_messages.append(f"Ошибка для студента {student_id}: {str(e)}")

        # Обрабатываем дополнительных студентов
        for student_id in extra_student_ids:
            try:
                # Проверяем, не было ли уже посещения сегодня
                existing_visit = db.query(Visits).filter(
                    and_(
                        Visits.student == student_id,
                        Visits.data >= visit_datetime.replace(hour=0, minute=0, second=0),
                        Visits.data < visit_datetime.replace(hour=23, minute=59, second=59)
                    )
                ).first()

                if existing_visit:
                    error_messages.append(f"Доп. студент ID {student_id} уже отмечен сегодня")
                    continue

                # Создаем запись о посещении
                visit = Visits(
                    data=visit_datetime,
                    trainer=trainer_id,
                    student=student_id,
                    place=schedule.training_place,
                    sport_discipline=schedule.sport_discipline,
                    shedule=schedule_id
                )

                db.add(visit)
                success_count += 1

            except Exception as e:
                error_messages.append(f"Ошибка для доп. студента {student_id}: {str(e)}")

        db.commit()

        response_data = {
            "status": "success",
            "message": f"Успешно сохранено {success_count} посещений",
            "saved_count": success_count
        }

        if error_messages:
            response_data["warnings"] = error_messages[:5]

        print(f"Successfully saved {success_count} visits")
        return JSONResponse(response_data)

    except Exception as e:
        db.rollback()
        print(f"Error in save_visits: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения посещений: {str(e)}")


# ===== КАЛЕНДАРЬ МЕРОПРИЯТИЙ =====

@app.get("/competitions/", response_class=HTMLResponse)
async def competitions_page(request: Request, db: Session = Depends(get_db)):
    """Главная страница календаря мероприятий"""
    return templates.TemplateResponse("competitions.html", {
        "request": request
    })


@app.get("/competitions/get-events")
async def get_events(year: int, month: int, db: Session = Depends(get_db)):
    """Получение мероприятий для конкретного месяца"""
    try:
        logger.debug(f"🔹 Получение мероприятий за {year}-{month}")

        # Получаем мероприятия за указанный месяц
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)

        logger.debug(f"🔹 Поиск мероприятий с {start_date} по {end_date}")

        # Используем правильное название класса - Сompetition (с русской С)
        competitions = db.query(Сompetition).filter(
            and_(
                Сompetition.date >= start_date,
                Сompetition.date < end_date
            )
        ).all()

        logger.debug(f"🔹 Найдено {len(competitions)} мероприятий")

        events = []
        for comp in competitions:
            events.append({
                "id": comp.id,
                "name": comp.name,
                "date": comp.date.isoformat() if comp.date else None,
                "address": comp.address or ""
            })

        return JSONResponse(events)

    except Exception as e:
        logger.error(f"❌ Ошибка в get_events: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ошибка получения мероприятий: {str(e)}")


@app.get("/competitions/get-day-events")
async def get_day_events(date: str, db: Session = Depends(get_db)):
    """Получение мероприятий на конкретную дату"""
    try:
        logger.debug(f"🔹 Получение мероприятий на дату: {date}")

        selected_date = datetime.fromisoformat(date).date()
        next_day = selected_date + timedelta(days=1)

        logger.debug(f"🔹 Поиск мероприятий с {selected_date} по {next_day}")

        competitions = db.query(Сompetition).filter(
            and_(
                Сompetition.date >= selected_date,
                Сompetition.date < next_day
            )
        ).all()

        logger.debug(f"🔹 Найдено {len(competitions)} мероприятий на эту дату")

        events = []
        for comp in competitions:
            event_time = ""
            if comp.date:
                event_time = comp.date.strftime("%H:%M")

            events.append({
                "id": comp.id,
                "name": comp.name,
                "date": comp.date.isoformat() if comp.date else None,
                "address": comp.address or "",
                "time": event_time
            })

        return JSONResponse(events)

    except Exception as e:
        logger.error(f"❌ Ошибка в get_day_events: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ошибка получения мероприятий: {str(e)}")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)