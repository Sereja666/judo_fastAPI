# api/trainers.py
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from database.schemas import get_db, Trainers, Sport
from config import templates

router = APIRouter()


@router.get("/edit-trainers", response_class=HTMLResponse)
async def edit_trainers_page(request: Request, db: Session = Depends(get_db)):
    """Главная страница редактирования тренеров"""
    trainers = db.query(Trainers).filter(Trainers.active == True).all()
    sports = db.query(Sport).all()

    return templates.TemplateResponse("edit_trainers.html", {
        "request": request,
        "trainers": trainers,
        "sports": sports
    })


@router.get("/get-trainer-data/{trainer_id}")
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


@router.post("/update-trainer")
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


@router.get("/debug-trainers")
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


@router.get("/debug-trainer-structure")
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