# student_edit.py
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker, Session
from typing import List, Optional
import os
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from database.models import Students, Sport, Trainers, engine

# Создаем сессию базы данных
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI(title="Student Editor")

# Создаем папку templates если её нет
if not os.path.exists("templates"):
    os.makedirs("templates")

templates = Jinja2Templates(directory="templates")


# Зависимость для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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


@app.get("/search-students-edit")
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


@router.post("/students/update")  # Без /api в начале
async def update_student_direct(
        request: Request,
        db: Session = Depends(get_db)
):
    try:
        data = await request.json()
        student_id = data.get('student_id')

        if not student_id:
            return JSONResponse({"success": False, "error": "Нет student_id"})

        student = db.query(Students).filter(Students.id == student_id).first()
        if not student:
            return JSONResponse({"success": False, "error": "Ученик не найден"})

        # Обновите поля...

        db.commit()
        return JSONResponse({"success": True, "message": "Сохранено"})

    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "error": str(e)})
    
# Добавьте модель для валидации данных
class StudentUpdate(BaseModel):
    student_id: int
    name: str
    birthday: Optional[str] = None
    sport_discipline: Optional[int] = None
    rang: Optional[str] = None
    sex: Optional[str] = None
    weight: Optional[int] = None
    reference1: Optional[str] = None
    reference2: Optional[str] = None
    reference3: Optional[str] = None
    head_trainer_id: Optional[int] = None
    second_trainer_id: Optional[int] = None
    price: Optional[int] = None
    payment_day: Optional[int] = None
    classes_remaining: Optional[int] = None
    expected_payment_date: Optional[str] = None
    telephone: Optional[str] = None
    parent1: Optional[int] = None
    parent2: Optional[int] = None
    date_start: Optional[str] = None
    telegram_id: Optional[int] = None

@app.post("/update-student")
async def update_student(student_data: StudentUpdate, db: Session = Depends(get_db)):
    """Обновление данных ученика"""
    try:
        # print(f"Получены данные для student_id: {student_data.student_id}")
        # print(f"Данные: {student_data.dict()}")
        logger.info(f"🔹 Получен запрос на обновление ученика {student_id}")
        # Логируем headers
        headers = dict(request.headers)
        logger.info(f"Заголовки запроса: {headers}")
        student = db.query(Students).filter(Students.id == student_data.student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Ученик не найден")
        
        # Обновляем поля
        student.name = student_data.name
        
        # Обработка дат с проверкой
        try:
            student.birthday = datetime.fromisoformat(student_data.birthday.replace('Z', '+00:00')) if student_data.birthday else None
        except:
            student.birthday = None
            
        student.sport_discipline = student_data.sport_discipline
        student.rang = student_data.rang
        student.sex = student_data.sex
        student.weight = student_data.weight
        
        try:
            student.reference1 = datetime.fromisoformat(student_data.reference1).date() if student_data.reference1 else None
        except:
            student.reference1 = None
            
        try:
            student.reference2 = datetime.fromisoformat(student_data.reference2).date() if student_data.reference2 else None
        except:
            student.reference2 = None
            
        try:
            student.reference3 = datetime.fromisoformat(student_data.reference3).date() if student_data.reference3 else None
        except:
            student.reference3 = None
            
        student.head_trainer_id = student_data.head_trainer_id
        student.second_trainer_id = student_data.second_trainer_id
        student.price = student_data.price
        student.payment_day = student_data.payment_day
        student.classes_remaining = student_data.classes_remaining
        
        try:
            student.expected_payment_date = datetime.fromisoformat(student_data.expected_payment_date).date() if student_data.expected_payment_date else None
        except:
            student.expected_payment_date = None
            
        student.telephone = student_data.telephone
        student.parent1 = student_data.parent1
        student.parent2 = student_data.parent2
        
        try:
            student.date_start = datetime.fromisoformat(student_data.date_start.replace('Z', '+00:00')) if student_data.date_start else None
        except:
            student.date_start = None
            
        student.telegram_id = student_data.telegram_id
        
        db.commit()
        
        return JSONResponse({"status": "success", "message": "Данные ученика успешно обновлены"})
    
    except Exception as e:
        db.rollback()
        print(f"Ошибка при сохранении: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка обновления: {str(e)}")

# Если запускаем этот файл отдельно
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)