# api/visits.py
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List
from datetime import datetime
from database.schemas import get_db, Trainers, Sport, Training_place, Schedule, Students_schedule, Students, Visits
from config import templates

router = APIRouter()

@router.get("/visits/", response_class=HTMLResponse)
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

@router.get("/visits/get-schedules-by-date")
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

@router.get("/visits/get-students-by-schedule")
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

@router.get("/visits/search-students")
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

@router.post("/visits/save-visits")
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