from config import templates, settings
# api/students.py
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional, List
from datetime import datetime
from database.schemas import get_db, Students, Sport, Trainers, Prices, Sports_rank, Belt_сolor
from config import templates
from logger_config import logger

router = APIRouter()


@router.get("/edit-students", response_class=HTMLResponse)
async def edit_students_page(request: Request, db: Session = Depends(get_db)):
    """Главная страница редактирования учеников"""
    students = db.query(Students).filter(Students.active == True).all()
    sports = db.query(Sport).all()
    trainers = db.query(Trainers).all()
    prices = db.query(Prices).all()
    sports_ranks = db.query(Sports_rank).all()
    belt_colors = db.query(Belt_сolor).all()

    return templates.TemplateResponse("edit_students.html", {
        "request": request,
        "students": students,
        "sports": sports,
        "trainers": trainers,
        "prices": prices,
        "sports_ranks": sports_ranks,
        "belt_colors": belt_colors
    })


@router.get("/edit-students/search-students")
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


@router.get("/edit-students/get-student-data/{student_id}")
async def get_student_data(student_id: int, db: Session = Depends(get_db)):
    """Получение данных ученика"""
    try:
        print(f"🔹 Запрос данных ученика ID: {student_id}")

        student = db.query(Students).filter(Students.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Ученик не найден")

        # Безопасное преобразование данных
        def safe_isoformat(date_obj):
            if date_obj and hasattr(date_obj, 'isoformat'):
                return date_obj.isoformat()
            return None

        student_data = {
            "id": student.id,
            "name": student.name or "",
            "birthday": safe_isoformat(student.birthday),
            "sport_discipline": student.sport_discipline,
            "rang": student.rang or "",
            "sports_rank": student.sports_rank,
            "sex": student.sex or "",
            "weight": student.weight,
            "head_trainer_id": student.head_trainer_id,
            "second_trainer_id": student.second_trainer_id,
            "price": student.price,
            "payment_day": student.payment_day,
            "classes_remaining": student.classes_remaining,
            "expected_payment_date": safe_isoformat(student.expected_payment_date),
            "telephone": student.telephone or "",
            "parent1": student.parent1,
            "parent2": student.parent2,
            "date_start": safe_isoformat(student.date_start),
            "telegram_id": student.telegram_id,
            "active": bool(student.active) if student.active is not None else True
        }

        logger.success(f"✅ Успешно загружены данные ученика: {student_data['name']}")
        return JSONResponse(student_data)

    except Exception as e:
        logger.error(f"❌ Ошибка загрузки данных ученика: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки данных: {str(e)}")


@router.post("/edit-students/update-student")
async def update_student(
        student_id: int = Form(...),
        name: str = Form(...),
        birthday: Optional[str] = Form(None),
        sport_discipline: Optional[str] = Form(None),
        rang: Optional[str] = Form(None),
        sports_rank: Optional[str] = Form(None),
        sex: Optional[str] = Form(None),
        weight: Optional[str] = Form(None),
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

        # Функция для безопасного преобразования
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

        # Обновляем поля
        student.name = name
        student.birthday = datetime.fromisoformat(birthday) if birthday else None
        student.sport_discipline = parse_int(sport_discipline)
        student.rang = parse_value(rang)
        student.sports_rank = parse_int(sports_rank)
        student.sex = parse_value(sex)
        student.weight = parse_int(weight)
        student.head_trainer_id = parse_int(head_trainer_id)
        student.second_trainer_id = parse_int(second_trainer_id)
        student.price = parse_int(price)
        student.payment_day = parse_int(payment_day)
        student.classes_remaining = parse_int(classes_remaining)
        student.expected_payment_date = datetime.fromisoformat(
            expected_payment_date).date() if expected_payment_date else None
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
        logger.error(f"Ошибка при сохранении: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка обновления: {str(e)}")


@router.post("/edit-students/create-student")
async def create_student(
        name: str = Form(...),
        birthday: Optional[str] = Form(None),
        sport_discipline: Optional[str] = Form(None),
        rang: Optional[str] = Form(None),
        sports_rank: Optional[str] = Form(None),
        sex: Optional[str] = Form(None),
        weight: Optional[str] = Form(None),
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
        print("🎯 Создание нового ученика")

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
            sports_rank=parse_int(sports_rank),
            sex=parse_value(sex),
            weight=parse_int(weight),
            head_trainer_id=parse_int(head_trainer_id),
            second_trainer_id=parse_int(second_trainer_id),
            price=parse_int(price),
            payment_day=parse_int(payment_day),
            classes_remaining=parse_int(classes_remaining),
            expected_payment_date=datetime.fromisoformat(
                expected_payment_date).date() if expected_payment_date else None,
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

        logger.info(f"✅ Создан новый ученик с ID: {new_student.id}, имя: {new_student.name}")

        return JSONResponse({
            "status": "success",
            "message": "Ученик успешно создан",
            "student_id": new_student.id
        })

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Ошибка при создании ученика: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ошибка создания: {str(e)}")


@router.get("/edit-students/get-prices")
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