import traceback

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
        # Получаем текущий день недели (с маленькой буквы как в базе)
        days_ru_lower = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
        today = datetime.now()
        today_weekday = days_ru_lower[today.weekday()]  # Python: понедельник=0

        logger.info(f"📅 Сегодня: {today.strftime('%Y-%m-%d')}, день недели в базе: '{today_weekday}'")

        # Получаем места с тренировками сегодня
        places = db.query(Training_place).join(
            Schedule, Schedule.training_place == Training_place.id
        ).filter(
            Schedule.day_week == today_weekday
        ).distinct().all()

        logger.info(f"🏢 Найдено мест с тренировками сегодня: {len(places)}")

        if places:
            for place in places:
                logger.info(f"  - {place.name} (ID: {place.id})")

        result = [{"id": place.id, "name": place.name} for place in places]
        return JSONResponse(result)

    except Exception as e:
        logger.error(f"❌ Ошибка получения мест тренировок: {str(e)}")
        import traceback
        logger.error(f"Подробности ошибки: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения мест: {str(e)}")


@router.get("/visits-today/get-trainings/{place_id}")
async def get_trainings_today(place_id: int, db: Session = Depends(get_db)):
    """Получение тренировок на сегодня для выбранного места"""
    try:
        # Получаем текущий день недели (с маленькой буквы)
        days_ru_lower = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
        today = datetime.now()
        today_weekday = days_ru_lower[today.weekday()]

        logger.info(f"🔍 Ищем тренировки для места ID: {place_id}, день: '{today_weekday}'")

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

        logger.info(f"📋 Найдено тренировок: {len(trainings)}")

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
        logger.info(f"👥 Запрос студентов для расписания ID: {schedule_id}")

        # Получаем информацию о тренировке
        training_info = db.query(
            Schedule.time_start,
            Schedule.day_week
        ).filter(Schedule.id == schedule_id).first()

        if training_info:
            logger.info(f"📅 Тренировка: день '{training_info.day_week}', время {training_info.time_start}")

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

        logger.info(f"📊 Найдено студентов в расписании: {len(students)}")

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

        logger.info(f"✅ Уже посещено сегодня: {len(visited_ids)} студентов")

        result = []
        for student in students:
            # Получаем эмодзи пояса
            belt_emoji = belts.get(student.rang, "⚪️")

            # Год рождения
            birth_year = student.birthday.year if student.birthday else ""

            is_visited = student.id in visited_ids

            result.append({
                "id": student.id,
                "name": student.name,
                "birth_year": birth_year,
                "belt_emoji": belt_emoji,
                "display_name": f"{belt_emoji} {student.name} {birth_year}",
                "is_visited": is_visited
            })

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"❌ Ошибка получения студентов: {str(e)}")
        import traceback
        logger.error(f"Подробности ошибки: {traceback.format_exc()}")
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

        logger.info(f"💾 Сохранение посещений для расписания: {schedule_id}")
        logger.info(f"👥 Студентов из расписания: {len(student_ids)}")
        logger.info(f"➕ Дополнительных студентов: {len(extra_students)}")

        if not schedule_id:
            raise HTTPException(status_code=400, detail="Не указано расписание")

        # Получаем информацию о тренировке
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule:
            raise HTTPException(status_code=404, detail="Расписание не найдено")

        # Создаем дату и время для посещения
        visit_datetime = datetime.combine(date.today(), schedule.time_start)

        # Получаем информацию о тренере (пока заглушка)
        # TODO: Получать trainer_id из сессии пользователя
        trainer = db.query(Trainers).filter(Trainers.telegram_id == 1).first()
        trainer_id = trainer.id if trainer else 1

        logger.info(f"👨‍🏫 Тренер: {trainer_id}, время: {visit_datetime}")

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
                        trainer=trainer_id,
                        student=student_id,
                        place=schedule.training_place,
                        sport_discipline=schedule.sport_discipline,
                        shedule=schedule_id
                    )
                    db.add(visit)
                    saved_count += 1

            except Exception as e:
                error_msg = f"Студент {student_id}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

        # Обрабатываем дополнительных студентов
        for student_data in extra_students:
            try:
                student_id = student_data.get("id")
                student_name = student_data.get("name", "Неизвестный")

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
                        trainer=trainer_id,
                        student=student_id,
                        place=schedule.training_place,
                        sport_discipline=schedule.sport_discipline,
                        shedule=schedule_id
                    )
                    db.add(visit)
                    saved_count += 1

            except Exception as e:
                error_msg = f"Доп. студент {student_name}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

        db.commit()

        logger.info(f"✅ Сохранено посещений: {saved_count}, ошибок: {len(errors)}")

        return JSONResponse({
            "status": "success",
            "message": f"Сохранено {saved_count} посещений",
            "saved_count": saved_count,
            "errors": errors[:5] if errors else []
        })

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Ошибка сохранения посещений: {str(e)}")
        import traceback
        logger.error(f"Подробности ошибки: {traceback.format_exc()}")
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