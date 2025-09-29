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


@app.get("/", response_class=HTMLResponse)
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


@app.get("/search-students")
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


@app.get("/get-schedules")
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


@app.get("/get-student-schedules")
async def get_student_schedules(student_id: int, db: Session = Depends(get_db)):
    """Получение текущего расписания ученика"""
    student_schedules = db.query(Students_schedule).filter(
        Students_schedule.student == student_id
    ).all()

    result = [ss.schedule for ss in student_schedules]
    return JSONResponse(result)


@app.post("/save-schedule")
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


@app.get("/student-schedule/{student_id}", response_class=HTMLResponse)
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)