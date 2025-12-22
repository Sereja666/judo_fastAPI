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
    """Обновление мероприятия - ВНИМАНИЕ: может сбрасывать статусы!"""
    try:
        logger.info(f"🔄 ОБНОВЛЕНИЕ мероприятия ID: {competition_id}")
        logger.info(f"   Новые студенты: {student_ids}")

        competition = db.query(Сompetition).filter(Сompetition.id == competition_id).first()
        if not competition:
            raise HTTPException(status_code=404, detail="Мероприятие не найдено")

        # Обновляем основные данные
        competition.name = name
        competition.address = address
        competition.date = datetime.fromisoformat(date)

        # ПРОВЕРЯЕМ ТЕКУЩИЕ СТАТУСЫ ПЕРЕД УДАЛЕНИЕМ
        current_students = db.query(Competition_student).filter(
            Competition_student.competition_id == competition_id
        ).all()

        logger.info("📋 ТЕКУЩИЕ СТАТУСЫ СТУДЕНТОВ ПЕРЕД ОБНОВЛЕНИЕМ:")
        for cs in current_students:
            status_map = {0: "0-не отправлено", 1: "1-отправлено", 2: "2-принято", 3: "3-отклонено"}
            status_text = status_map.get(cs.participation, f"{cs.participation}-неизвестно")
            logger.info(f"   Студент {cs.student_id}: статус {status_text}")

        # Удаляем старых студентов и добавляем новых
        db.query(Competition_student).filter(
            Competition_student.competition_id == competition_id
        ).delete()

        # ВОССТАНАВЛИВАЕМ СТАТУСЫ при добавлении
        for student_id in student_ids:
            # Ищем старый статус этого студента
            old_status = 0  # по умолчанию
            for cs in current_students:
                if cs.student_id == student_id:
                    old_status = cs.participation
                    break

            competition_student = Competition_student(
                competition_id=competition_id,
                student_id=student_id,
                participation=old_status  # ВОССТАНАВЛИВАЕМ СТАТУС!
            )
            db.add(competition_student)
            logger.info(f"   ➕ Студент {student_id} добавлен со статусом {old_status}")

        # Остальное без изменений...
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

        logger.info(f"✅ Мероприятие {competition_id} обновлено")

        return JSONResponse({
            "status": "success",
            "message": "Мероприятие успешно обновлено"
        })

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Ошибка в update_competition: {str(e)}")
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
    """Отправка приглашений на мероприятие - ТОЛЬКО 0 → 1"""
    try:
        logger.info(f"🚀 НАЧАЛО отправки приглашений для мероприятия ID: {competition_id}")

        # Получаем мероприятие
        competition = db.query(Сompetition).filter(Сompetition.id == competition_id).first()
        if not competition:
            logger.error(f"❌ Мероприятие {competition_id} не найдено")
            raise HTTPException(status_code=404, detail="Мероприятие не найдено")

        logger.info(f"📋 Мероприятие: {competition.name} (ID: {competition.id})")

        # Получаем ВСЕХ приглашенных студентов С ПРОСМОТРОМ ТЕКУЩИХ СТАТУСОВ
        competition_students = db.query(Competition_student).filter(
            Competition_student.competition_id == competition_id
        ).all()

        logger.info(f"👥 Найдено студентов: {len(competition_students)}")

        # ЛОГИРУЕМ ВСЕ ТЕКУЩИЕ СТАТУСЫ ПЕРЕД ИЗМЕНЕНИЯМИ
        logger.info("📊 ТЕКУЩИЕ СТАТУСЫ СТУДЕНТОВ:")
        for cs in competition_students:
            status_map = {0: "0-не отправлено", 1: "1-отправлено", 2: "2-принято", 3: "3-отклонено"}
            status_text = status_map.get(cs.participation, f"{cs.participation}-неизвестно")
            logger.info(f"   Студент ID {cs.student_id}: статус = {status_text}")

        if not competition_students:
            logger.warning("⚠️ Нет студентов для отправки приглашений")
            return JSONResponse({
                "status": "warning",
                "message": "Нет приглашенных студентов для отправки приглашений"
            })

        # Счетчики
        updated_0_to_1 = 0
        already_1 = 0
        already_2 = 0
        already_3 = 0
        other_status = 0

        # ОЧЕНЬ ПРОСТАЯ ЛОГИКА: меняем ТОЛЬКО 0 → 1
        for comp_student in competition_students:
            current = comp_student.participation
            student_id = comp_student.student_id

            if current == 0:
                # МЕНЯЕМ ТОЛЬКО 0 на 1
                old_status = comp_student.participation
                comp_student.participation = 1
                updated_0_to_1 += 1
                logger.info(f"   ✅ Студент {student_id}: {old_status} → {comp_student.participation} (ОТПРАВЛЕНО)")

            elif current == 1:
                already_1 += 1
                logger.info(f"   ⏸️ Студент {student_id}: остаётся {current} (уже отправлено)")

            elif current == 2:
                already_2 += 1
                logger.info(f"   🔒 Студент {student_id}: остаётся {current} (ПРИНЯТО - НЕ ТРОГАЕМ!)")
                # ЯВНО проверяем, что не меняем
                assert comp_student.participation == 2, f"Статус студента {student_id} изменился на {comp_student.participation}!"

            elif current == 3:
                already_3 += 1
                logger.info(f"   🔒 Студент {student_id}: остаётся {current} (ОТКЛОНЕНО - НЕ ТРОГАЕМ!)")
                # ЯВНО проверяем, что не меняем
                assert comp_student.participation == 3, f"Статус студента {student_id} изменился на {comp_student.participation}!"

            else:
                other_status += 1
                logger.warning(f"   ❓ Студент {student_id}: неизвестный статус {current}")

        # Сохраняем изменения
        db.commit()

        # ПРОВЕРЯЕМ СТАТУСЫ ПОСЛЕ ИЗМЕНЕНИЙ
        logger.info("📊 СТАТУСЫ СТУДЕНТОВ ПОСЛЕ ОБРАБОТКИ:")
        db.refresh(competition)  # Обновляем объект
        check_students = db.query(Competition_student).filter(
            Competition_student.competition_id == competition_id
        ).all()

        for cs in check_students:
            status_map = {0: "0-не отправлено", 1: "1-отправлено", 2: "2-принято", 3: "3-отклонено"}
            status_text = status_map.get(cs.participation, f"{cs.participation}-неизвестно")
            logger.info(f"   Студент ID {cs.student_id}: статус = {status_text}")

        # Формируем итоговое сообщение
        total = len(competition_students)
        message_parts = []

        if updated_0_to_1 > 0:
            message_parts.append(f"Отправлено {updated_0_to_1} новых приглашений")

        if already_2 > 0:
            message_parts.append(f"{already_2} уже приняли приглашение")

        if already_3 > 0:
            message_parts.append(f"{already_3} уже отклонили приглашение")

        if already_1 > 0:
            message_parts.append(f"{already_1} уже имеют отправленное приглашение")

        if not message_parts:
            message_parts.append("Нет изменений")

        message = ". ".join(message_parts)

        logger.info(f"📈 ИТОГ: {message}")
        logger.info(
            f"   Всего: {total}, 0→1: {updated_0_to_1}, уже 1: {already_1}, принято(2): {already_2}, отклонено(3): {already_3}")

        return JSONResponse({
            "status": "success",
            "message": message,
            "details": {
                "competition_name": competition.name,
                "total_students": total,
                "updated_0_to_1": updated_0_to_1,
                "already_1": already_1,
                "already_2": already_2,
                "already_3": already_3,
                "other_status": other_status,
                "logic": "ИЗМЕНЕНЫ ТОЛЬКО СТАТУСЫ 0 → 1. Статусы 1, 2, 3 НЕ ИЗМЕНЯЮТСЯ."
            }
        })

    except Exception as e:
        db.rollback()
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА в send_invitations: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
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