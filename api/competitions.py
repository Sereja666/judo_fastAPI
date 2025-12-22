# api/competitions.py
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List
from datetime import datetime, timedelta
from config import templates, settings


from database.models import Сompetition, MedCertificat_type, Students, Trainers, \
    Competition_student, Сompetition_trainer, Сompetition_MedCertificat, get_db
from config import templates
from logger_config import logger

router = APIRouter()

@router.get("/competitions/", response_class=HTMLResponse)
async def competitions_page(request: Request, db: Session = Depends(get_db)):
    """Главная страница календаря мероприятий"""
    return templates.TemplateResponse("competitions.html", {
        "request": request
    })

@router.get("/competitions/get-events")
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

@router.get("/competitions/get-day-events")
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

@router.get("/competitions/get-all-data")
async def get_all_competition_data(db: Session = Depends(get_db)):
    """Получение всех данных для формы мероприятия"""
    try:
        # Получаем типы медицинских справок
        med_cert_types = db.query(MedCertificat_type).all()
        # Получаем всех активных учеников
        students = db.query(Students).filter(Students.active == True).all()
        # Получаем всех активных тренеров
        trainers = db.query(Trainers).filter(Trainers.active == True).all()

        result = {
            "med_cert_types": [{"id": cert.id, "name": cert.name_cert} for cert in med_cert_types],
            "students": [{"id": student.id, "name": student.name} for student in students],
            "trainers": [{"id": trainer.id, "name": trainer.name} for trainer in trainers]
        }

        return JSONResponse(result)

    except Exception as e:
        print(f"Error in get_all_competition_data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения данных: {str(e)}")

@router.get("/competitions/get-competition-data/{competition_id}")
async def get_competition_data(competition_id: int, db: Session = Depends(get_db)):
    """Получение данных конкретного мероприятия"""
    try:
        competition = db.query(Сompetition).filter(Сompetition.id == competition_id).first()
        if not competition:
            raise HTTPException(status_code=404, detail="Мероприятие не найдено")

        # Получаем приглашенных студентов
        competition_students = db.query(Competition_student).filter(
            Competition_student.competition_id == competition_id
        ).all()

        # Получаем ответственных тренеров
        competition_trainers = db.query(Сompetition_trainer).filter(
            Сompetition_trainer.competition_id == competition_id
        ).all()

        # Получаем требуемые справки
        competition_certificates = db.query(Сompetition_MedCertificat).filter(
            Сompetition_MedCertificat.competition_id == competition_id
        ).all()

        result = {
            "competition": {
                "id": competition.id,
                "name": competition.name,
                "address": competition.address or "",
                "date": competition.date.isoformat() if competition.date else None
            },
            "students": [cs.student_id for cs in competition_students],
            "trainers": [ct.trainer_id for ct in competition_trainers],
            "certificates": [cmc.med_certificat_id for cmc in competition_certificates]
        }

        return JSONResponse(result)

    except Exception as e:
        print(f"Error in get_competition_data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения данных мероприятия: {str(e)}")

@router.post("/competitions/create-competition")
async def create_competition(
        name: str = Form(...),
        address: str = Form(None),
        date: str = Form(...),
        student_ids: List[int] = Form([]),
        trainer_ids: List[int] = Form([]),
        certificate_ids: List[int] = Form([]),
        db: Session = Depends(get_db)
):
    """Создание нового мероприятия"""
    try:
        # Создаем мероприятие
        new_competition = Сompetition(
            name=name,
            address=address,
            date=datetime.fromisoformat(date)
        )
        db.add(new_competition)
        db.flush()  # Получаем ID созданного мероприятия

        # Добавляем студентов
        for student_id in student_ids:
            competition_student = Competition_student(
                competition_id=new_competition.id,
                student_id=student_id
            )
            db.add(competition_student)

        # Добавляем тренеров
        for trainer_id in trainer_ids:
            competition_trainer = Сompetition_trainer(
                competition_id=new_competition.id,
                trainer_id=trainer_id
            )
            db.add(competition_trainer)

        # Добавляем справки
        for cert_id in certificate_ids:
            competition_cert = Сompetition_MedCertificat(
                competition_id=new_competition.id,
                med_certificat_id=cert_id
            )
            db.add(competition_cert)

        db.commit()

        return JSONResponse({
            "status": "success",
            "message": "Мероприятие успешно создано",
            "competition_id": new_competition.id
        })

    except Exception as e:
        db.rollback()
        print(f"Error in create_competition: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка создания мероприятия: {str(e)}")

@router.post("/competitions/update-competition/{competition_id}")
async def update_competition(
        competition_id: int,
        name: str = Form(...),
        address: str = Form(None),
        date: str = Form(...),
        student_ids: List[int] = Form([]),
        trainer_ids: List[int] = Form([]),
        certificate_ids: List[int] = Form([]),
        db: Session = Depends(get_db)
):
    """Обновление мероприятия"""
    try:
        competition = db.query(Сompetition).filter(Сompetition.id == competition_id).first()
        if not competition:
            raise HTTPException(status_code=404, detail="Мероприятие не найдено")

        # Обновляем основные данные
        competition.name = name
        competition.address = address
        competition.date = datetime.fromisoformat(date)

        # Удаляем старых студентов и добавляем новых
        db.query(Competition_student).filter(
            Competition_student.competition_id == competition_id
        ).delete()

        for student_id in student_ids:
            competition_student = Competition_student(
                competition_id=competition_id,
                student_id=student_id
            )
            db.add(competition_student)

        # Удаляем старых тренеров и добавляем новых
        db.query(Сompetition_trainer).filter(
            Сompetition_trainer.competition_id == competition_id
        ).delete()

        for trainer_id in trainer_ids:
            competition_trainer = Сompetition_trainer(
                competition_id=competition_id,
                trainer_id=trainer_id
            )
            db.add(competition_trainer)

        # Удаляем старые справки и добавляем новые
        db.query(Сompetition_MedCertificat).filter(
            Сompetition_MedCertificat.competition_id == competition_id
        ).delete()

        for cert_id in certificate_ids:
            competition_cert = Сompetition_MedCertificat(
                competition_id=competition_id,
                med_certificat_id=cert_id
            )
            db.add(competition_cert)

        db.commit()

        return JSONResponse({
            "status": "success",
            "message": "Мероприятие успешно обновлено"
        })

    except Exception as e:
        db.rollback()
        print(f"Error in update_competition: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка обновления мероприятия: {str(e)}")


# Добавьте в competitions.py новый эндпоинт
@router.delete("/competitions/delete-competition/{competition_id}")
async def delete_competition(
        competition_id: int,
        db: Session = Depends(get_db)
):
    """Удаление мероприятия"""
    try:
        competition = db.query(Сompetition).filter(Сompetition.id == competition_id).first()
        if not competition:
            raise HTTPException(status_code=404, detail="Мероприятие не найдено")

        # Удаляем связанные записи
        db.query(Competition_student).filter(
            Competition_student.competition_id == competition_id
        ).delete()

        db.query(Сompetition_trainer).filter(
            Сompetition_trainer.competition_id == competition_id
        ).delete()

        db.query(Сompetition_MedCertificat).filter(
            Сompetition_MedCertificat.competition_id == competition_id
        ).delete()

        # Удаляем само мероприятие
        db.delete(competition)
        db.commit()

        return JSONResponse({
            "status": "success",
            "message": "Мероприятие успешно удалено"
        })

    except Exception as e:
        db.rollback()
        print(f"Error in delete_competition: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка удаления мероприятия: {str(e)}")


@router.post("/competitions/send-invitations/{competition_id}")
async def send_invitations(
        competition_id: int,
        db: Session = Depends(get_db)
):
    """Отправка приглашений на мероприятие"""
    try:
        logger.debug(f"🔹 Отправка приглашений для мероприятия ID: {competition_id}")

        # Получаем мероприятие
        competition = db.query(Сompetition).filter(Сompetition.id == competition_id).first()
        if not competition:
            raise HTTPException(status_code=404, detail="Мероприятие не найдено")

        # Получаем всех приглашенных студентов
        competition_students = db.query(Competition_student).filter(
            Competition_student.competition_id == competition_id
        ).all()

        if not competition_students:
            return JSONResponse({
                "status": "warning",
                "message": "Нет приглашенных студентов для отправки приглашений"
            })

        # Статистика
        total_students = len(competition_students)
        updated_count = 0  # статус изменён с 0 на 1
        already_sent_count = 0  # уже статус 1
        already_responded_count = 0  # статусы 2 или 3
        not_changed_ids = []  # ID студентов, чей статус не изменился

        # Простая и понятная логика:
        for comp_student in competition_students:
            current_status = comp_student.participation

            if current_status == 0:
                # Меняем только с 0 на 1
                comp_student.participation = 1
                updated_count += 1
                logger.debug(f"   Студент {comp_student.student_id}: 0 → 1 (отправлено)")

            elif current_status == 1:
                # Уже отправлено - ничего не делаем
                already_sent_count += 1
                not_changed_ids.append(comp_student.student_id)
                logger.debug(f"   Студент {comp_student.student_id}: остаётся 1 (уже отправлено)")

            elif current_status == 2 or current_status == 3:
                # Уже ответили (2=принято, 3=отклонено) - НИЧЕГО НЕ ДЕЛАЕМ
                already_responded_count += 1
                not_changed_ids.append(comp_student.student_id)
                status_text = "принято" if current_status == 2 else "отклонено"
                logger.debug(f"   Студент {comp_student.student_id}: остаётся {current_status} ({status_text})")

            else:
                # Неизвестный статус - ничего не делаем
                not_changed_ids.append(comp_student.student_id)
                logger.warning(f"   Студент {comp_student.student_id}: неизвестный статус {current_status}")

        db.commit()

        # Формируем сообщение
        if updated_count > 0:
            message = f"Приглашения отправлены {updated_count} студентам"
            if already_responded_count > 0:
                message += f" ({already_responded_count} уже ответили ранее)"
            if already_sent_count > 0:
                message += f" ({already_sent_count} уже имеют отправленное приглашение)"
        else:
            if already_responded_count > 0:
                message = f"Все студенты уже ответили на приглашения ({already_responded_count} чел.)"
            elif already_sent_count > 0:
                message = f"Приглашения уже отправлены всем студентам ({already_sent_count} чел.)"
            else:
                message = "Нет студентов для отправки приглашений"

        logger.info(f"✅ Итог отправки приглашений для '{competition.name}': {message}")

        return JSONResponse({
            "status": "success",
            "message": message,
            "details": {
                "competition_name": competition.name,
                "total_students": total_students,
                "updated_count": updated_count,  # изменили с 0 на 1
                "already_sent_count": already_sent_count,  # уже 1
                "already_responded_count": already_responded_count,  # 2 или 3
                "not_changed_students": not_changed_ids,
                "logic": "Меняем только статус 0 → 1. Статусы 1, 2, 3 не изменяются."
            }
        })

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Ошибка в send_invitations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка отправки приглашений: {str(e)}")


@router.get("/competitions/get-invitations-status/{competition_id}")
async def get_invitations_status(
        competition_id: int,
        db: Session = Depends(get_db)
):
    """Получение статуса приглашений на мероприятие"""
    try:
        competition = db.query(Сompetition).filter(Сompetition.id == competition_id).first()
        if not competition:
            raise HTTPException(status_code=404, detail="Мероприятие не найдено")

        # Получаем статусы приглашений с именами студентов
        competition_students = db.query(
            Competition_student,
            Students.name
        ).join(
            Students, Competition_student.student_id == Students.id
        ).filter(
            Competition_student.competition_id == competition_id
        ).all()

        status_counts = {
            "not_processed": 0,  # 0 - необработанно
            "sent": 0,  # 1 - отправлено
            "accepted": 0,  # 2 - принято
            "declined": 0,  # 3 - отклонено
            "total": len(competition_students)
        }

        student_statuses = []

        for comp_student, student_name in competition_students:
            # Считаем статусы
            if comp_student.participation == 0:
                status_counts["not_processed"] += 1
                status_text = "Не отправлено"
                status_class = "danger"
            elif comp_student.participation == 1:
                status_counts["sent"] += 1
                status_text = "Отправлено (ждём ответ)"
                status_class = "warning"
            elif comp_student.participation == 2:
                status_counts["accepted"] += 1
                status_text = "Принято ✓"
                status_class = "success"
            elif comp_student.participation == 3:
                status_counts["declined"] += 1
                status_text = "Отклонено ✗"
                status_class = "danger"
            else:
                status_text = "Неизвестно"
                status_class = "secondary"

            student_statuses.append({
                "student_id": comp_student.student_id,
                "student_name": student_name,
                "participation": comp_student.participation,
                "status_id": comp_student.status_id,
                "status_text": status_text,
                "status_class": status_class
            })

        return {
            "status": "success",
            "competition_name": competition.name,
            "competition_date": competition.date.isoformat() if competition.date else None,
            "status_counts": status_counts,
            "students": student_statuses
        }

    except Exception as e:
        logger.error(f"❌ Ошибка в get_invitations_status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения статуса приглашений: {str(e)}")