from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import Optional, List
from datetime import datetime, time, date
import json

from database.models import get_db, Students, Schedule, Training_place, Sport, Trainers, Students_schedule, Visits
from config import templates
from logger_config import logger

router = APIRouter()


@router.get("/visits-today/", response_class=HTMLResponse)
async def visits_today_page(request: Request):
    """Страница посещений сегодня (адаптирована для смартфонов)"""
    return templates.TemplateResponse("visits_today.html", {
        "request": request,
        "page_title": "Посещения сегодня"
    })


@router.get("/visits-today/get-places")
async def get_places_today(db: Session = Depends(get_db)):
    """Получение мест тренировок, где есть занятия сегодня"""
    try:
        # Получаем текущий день недели
        days_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        today = datetime.now()
        today_weekday = days_ru[today.weekday()]  # Python: понедельник=0

        # Получаем места с тренировками сегодня
        places = db.query(Training_place).join(
            Schedule, Schedule.training_place == Training_place.id
        ).filter(
            Schedule.day_week == today_weekday
        ).distinct().all()

        result = [{"id": place.id, "name": place.name} for place in places]
        return JSONResponse(result)

    except Exception as e:
        logger.error(f"❌ Ошибка получения мест тренировок: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения мест: {str(e)}")


@router.get("/visits-today/get-trainings/{place_id}")
async def get_trainings_today(place_id: int, db: Session = Depends(get_db)):
    """Получение тренировок на сегодня для выбранного места"""
    try:
        # Получаем текущий день недели
        days_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        today = datetime.now()
        today_weekday = days_ru[today.weekday()]

        # Получаем тренировки на сегодня
        trainings = db.query(
            Schedule.id,
            Schedule.time_start,
            Schedule.time_end,
            Sport.name.label("sport_name")
        ).join(
            Sport, Schedule.sport_discipline == Sport.id
        ).filter(
            and_(
                Schedule.training_place == place_id,
                Schedule.day_week == today_weekday
            )
        ).order_by(Schedule.time_start).all()

        result = []
        for training in trainings:
            result.append({
                "id": training.id,
                "time_start": training.time_start.strftime("%H:%M") if training.time_start else None,
                "time_end": training.time_end.strftime("%H:%M") if training.time_end else None,
                "sport_name": training.sport_name,
                "display": f"{training.time_start.strftime('%H:%M')}-{training.time_end.strftime('%H:%M')} ({training.sport_name})"
            })

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"❌ Ошибка получения тренировок: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения тренировок: {str(e)}")


@router.get("/visits-today/get-students/{schedule_id}")
async def get_students_for_training(schedule_id: int, db: Session = Depends(get_db)):
    """Получение студентов, записанных на тренировку"""
    try:
        # Получаем студентов, привязанных к расписанию
        students = db.query(
            Students.id,
            Students.name,
            Students.birthday,
            Students.rang
        ).join(
            Students_schedule, Students_schedule.student == Students.id
        ).filter(
            and_(
                Students_schedule.schedule == schedule_id,
                Students.active == True
            )
        ).order_by(Students.name).all()

        # Получаем эмодзи поясов
        from database.models import Belt_сolor
        belts = {belt.id: belt.color for belt in db.query(Belt_сolor).all()}

        # Получаем уже посещенных студентов сегодня
        today = date.today()
        visited_students = db.query(Visits.student).filter(
            and_(
                Visits.shedule == schedule_id,
                Visits.data >= datetime.combine(today, time.min),
                Visits.data <= datetime.combine(today, time.max)
            )
        ).all()
        visited_ids = {v.student for v in visited_students}

        result = []
        for student in students:
            # Получаем эмодзи пояса
            belt_emoji = belts.get(student.rang, "⚪️")

            # Год рождения
            birth_year = student.birthday.year if student.birthday else ""

            result.append({
                "id": student.id,
                "name": student.name,
                "birth_year": birth_year,
                "belt_emoji": belt_emoji,
                "display_name": f"{belt_emoji} {student.name} {birth_year}",
                "is_visited": student.id in visited_ids
            })

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"❌ Ошибка получения студентов: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения студентов: {str(e)}")


@router.get("/visits-today/search-extra-student")
async def search_extra_student(query: str, db: Session = Depends(get_db)):
    """Поиск ученика для добавления вне расписания"""
    try:
        if len(query) < 2:
            return JSONResponse([])

        students = db.query(
            Students.id,
            Students.name,
            Students.birthday,
            Students.rang
        ).filter(
            and_(
                Students.active == True,
                or_(
                    Students.name.ilike(f"%{query}%"),
                    Students.name.ilike(f"{query}%")
                )
            )
        ).limit(10).all()

        # Получаем эмодзи поясов
        from database.models import Belt_сolor
        belts = {belt.id: belt.color for belt in db.query(Belt_сolor).all()}

        result = []
        for student in students:
            belt_emoji = belts.get(student.rang, "⚪️")
            birth_year = student.birthday.year if student.birthday else ""

            result.append({
                "id": student.id,
                "name": student.name,
                "birth_year": birth_year,
                "belt_emoji": belt_emoji,
                "display": f"{belt_emoji} {student.name} {birth_year}"
            })

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"❌ Ошибка поиска ученика: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка поиска: {str(e)}")


@router.post("/visits-today/save-attendance")
async def save_attendance(
        request: Request,
        db: Session = Depends(get_db)
):
    """Сохранение посещений"""
    try:
        form_data = await request.json()

        schedule_id = form_data.get("schedule_id")
        student_ids = form_data.get("student_ids", [])
        extra_students = form_data.get("extra_students", [])
        trainer_id = form_data.get("trainer_id")  # TODO: Получать из сессии

        if not schedule_id:
            raise HTTPException(status_code=400, detail="Не указано расписание")

        # Получаем информацию о тренировке
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule:
            raise HTTPException(status_code=404, detail="Расписание не найдено")

        # Создаем дату и время для посещения
        visit_datetime = datetime.combine(date.today(), schedule.time_start)

        # Сохраняем посещения для студентов из расписания
        saved_count = 0
        errors = []

        # Сначала обрабатываем обычных студентов
        for student_id in student_ids:
            try:
                # Проверяем, не было ли уже посещения сегодня
                existing = db.query(Visits).filter(
                    and_(
                        Visits.student == student_id,
                        Visits.shedule == schedule_id,
                        Visits.data >= datetime.combine(date.today(), time.min),
                        Visits.data <= datetime.combine(date.today(), time.max)
                    )
                ).first()

                if not existing:
                    visit = Visits(
                        data=visit_datetime,
                        trainer=trainer_id or 1,  # TODO: Заменить на реального тренера
                        student=student_id,
                        place=schedule.training_place,
                        sport_discipline=schedule.sport_discipline,
                        shedule=schedule_id
                    )
                    db.add(visit)
                    saved_count += 1

            except Exception as e:
                errors.append(f"Студент {student_id}: {str(e)}")

        # Обрабатываем дополнительных студентов
        for student_data in extra_students:
            try:
                student_id = student_data.get("id")

                if not student_id:
                    continue

                # Проверяем, не было ли уже посещения сегодня
                existing = db.query(Visits).filter(
                    and_(
                        Visits.student == student_id,
                        Visits.shedule == schedule_id,
                        Visits.data >= datetime.combine(date.today(), time.min),
                        Visits.data <= datetime.combine(date.today(), time.max)
                    )
                ).first()

                if not existing:
                    visit = Visits(
                        data=visit_datetime,
                        trainer=trainer_id or 1,  # TODO: Заменить на реального тренера
                        student=student_id,
                        place=schedule.training_place,
                        sport_discipline=schedule.sport_discipline,
                        shedule=schedule_id
                    )
                    db.add(visit)
                    saved_count += 1

            except Exception as e:
                errors.append(f"Доп. студент {student_data.get('name')}: {str(e)}")

        db.commit()

        return JSONResponse({
            "status": "success",
            "message": f"Сохранено {saved_count} посещений",
            "saved_count": saved_count,
            "errors": errors[:5] if errors else []
        })

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Ошибка сохранения посещений: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения: {str(e)}")


@router.get("/visits-today/get-attendance-status/{schedule_id}")
async def get_attendance_status(schedule_id: int, db: Session = Depends(get_db)):
    """Получение статуса посещений на тренировке"""
    try:
        today = date.today()

        # Получаем тренировку
        training = db.query(
            Schedule.time_start,
            Schedule.time_end,
            Training_place.name.label("place_name"),
            Sport.name.label("sport_name")
        ).join(
            Training_place, Schedule.training_place == Training_place.id
        ).join(
            Sport, Schedule.sport_discipline == Sport.id
        ).filter(Schedule.id == schedule_id).first()

        if not training:
            raise HTTPException(status_code=404, detail="Тренировка не найдена")

        # Получаем всех кто пришел (включая дополнительных)
        visited = db.query(
            Visits.student,
            Students.name,
            Students.birthday,
            Students.rang
        ).join(
            Students, Visits.student == Students.id
        ).filter(
            and_(
                Visits.shedule == schedule_id,
                Visits.data >= datetime.combine(today, time.min),
                Visits.data <= datetime.combine(today, time.max)
            )
        ).all()

        # Получаем всех кто должен был прийти по расписанию
        scheduled = db.query(
            Students.id,
            Students.name,
            Students.birthday,
            Students.rang
        ).join(
            Students_schedule, Students_schedule.student == Students.id
        ).filter(
            and_(
                Students_schedule.schedule == schedule_id,
                Students.active == True
            )
        ).all()

        # Получаем эмодзи поясов
        from database.models import Belt_сolor
        belts = {belt.id: belt.color for belt in db.query(Belt_сolor).all()}

        visited_ids = {v.student for v in visited}

        # Формируем списки
        present_students = []
        absent_students = []

        # Обрабатываем посещенных
        for visit in visited:
            belt_emoji = belts.get(visit.rang, "⚪️")
            birth_year = visit.birthday.year if visit.birthday else ""
            present_students.append({
                "id": visit.student,
                "name": visit.name,
                "birth_year": birth_year,
                "belt_emoji": belt_emoji,
                "display": f"{belt_emoji} {visit.name} {birth_year}"
            })

        # Обрабатываем отсутствующих
        for student in scheduled:
            if student.id not in visited_ids:
                belt_emoji = belts.get(student.rang, "⚪️")
                birth_year = student.birthday.year if student.birthday else ""
                absent_students.append({
                    "id": student.id,
                    "name": student.name,
                    "birth_year": birth_year,
                    "belt_emoji": belt_emoji,
                    "display": f"{belt_emoji} {student.name} {birth_year}"
                })

        return JSONResponse({
            "training_info": {
                "place_name": training.place_name,
                "time_start": training.time_start.strftime("%H:%M"),
                "time_end": training.time_end.strftime("%H:%M"),
                "sport_name": training.sport_name
            },
            "present_students": present_students,
            "absent_students": absent_students,
            "stats": {
                "total": len(scheduled) + len(present_students) - len(
                    visited_ids.intersection({s.id for s in scheduled})),
                "present": len(present_students),
                "absent": len(absent_students)
            }
        })

    except Exception as e:
        logger.error(f"❌ Ошибка получения статуса: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения статуса: {str(e)}")