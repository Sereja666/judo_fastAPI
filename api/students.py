from app_notif import models
from config import templates, settings
# api/students.py
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, select, distinct, func
from typing import Optional, List
from datetime import datetime
from database.models import get_db, Students, Sport, Trainers, Prices, Sports_rank, Belt_сolor, MedCertificat_received, \
    MedCertificat_type, Competition_student, Сompetition, Students_parents, Tg_notif_user, get_db_async
from config import templates
from db_handler.db_funk import get_user_permissions, process_payment_via_web
from logger_config import logger
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Dict, Any


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


# api/students.py - найдите endpoint для сохранения ученика
@router.put("/api/student/{student_id}")
@router.post("/api/student/{student_id}")
async def update_student(
        student_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db_async)
):
    """Обновление данных ученика"""
    try:
        # Проверяем авторизацию
        user_info = getattr(request.state, 'user', None)
        if not user_info or not user_info.get("authenticated"):
            raise HTTPException(status_code=401, detail="Не авторизован")

        # Пробуем получить данные как form-data (обычная форма)
        form_data = await request.form()

        # Если это не form-data, пробуем как JSON
        if not form_data:
            try:
                data = await request.json()
            except:
                data = {}
        else:
            data = dict(form_data)

        # Находим ученика
        student = await db.execute(
            select(models.Students)
            .filter(models.Students.id == student_id)
        )
        student = student.scalar_one_or_none()

        if not student:
            raise HTTPException(status_code=404, detail="Ученик не найден")

        # Обновляем поля
        update_fields = [
            'name', 'birthday', 'sport_discipline', 'rang', 'sports_rank',
            'sex', 'weight', 'head_trainer_id', 'second_trainer_id',
            'price', 'payment_day', 'classes_remaining', 'expected_payment_date',
            'telephone', 'parent1', 'parent2', 'date_start', 'telegram_id', 'active'
        ]

        for field in update_fields:
            if field in data:
                value = data[field]

                # Преобразуем типы данных
                if field in ['price', 'payment_day', 'classes_remaining', 'weight', 'telegram_id']:
                    if value is not None and value != '':
                        try:
                            value = int(value)
                        except (ValueError, TypeError):
                            value = None
                    else:
                        value = None

                elif field in ['birthday', 'date_start', 'expected_payment_date']:
                    if value and value != '':
                        try:
                            # Преобразуем строку в дату/время
                            if 'T' in value:
                                # Формат: YYYY-MM-DDTHH:MM
                                value = datetime.strptime(value, '%Y-%m-%dT%H:%M')
                            else:
                                # Формат: YYYY-MM-DD
                                value = datetime.strptime(value, '%Y-%m-%d').date()
                        except:
                            value = None
                    else:
                        value = None

                elif field == 'active':
                    value = str(value).lower() in ['true', '1', 'yes', 'on']

                setattr(student, field, value)

        # Сохраняем изменения
        await db.commit()
        await db.refresh(student)

        return {
            "success": True,
            "message": "Данные ученика обновлены",
            "student_id": student.id,
            "student_name": student.name
        }

    except Exception as e:
        logger.error(f"Error updating student: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка обновления: {str(e)}")
# @router.post("/edit-students/update-student")
# async def update_student(
#         student_id: int = Form(...),
#         name: str = Form(...),
#         birthday: Optional[str] = Form(None),
#         sport_discipline: Optional[str] = Form(None),
#         rang: Optional[str] = Form(None),
#         sports_rank: Optional[str] = Form(None),
#         sex: Optional[str] = Form(None),
#         weight: Optional[str] = Form(None),
#         head_trainer_id: Optional[str] = Form(None),
#         second_trainer_id: Optional[str] = Form(None),
#         price: Optional[str] = Form(None),
#         payment_day: Optional[str] = Form(None),
#         classes_remaining: Optional[str] = Form(None),
#         expected_payment_date: Optional[str] = Form(None),
#         telephone: Optional[str] = Form(None),
#         parent1: Optional[str] = Form(None),
#         parent2: Optional[str] = Form(None),
#         date_start: Optional[str] = Form(None),
#         telegram_id: Optional[str] = Form(None),
#         active: Optional[str] = Form(None),
#         db: Session = Depends(get_db)
# ):
#     """Обновление данных ученика"""
#     try:
#         print(f"Получены данные для student_id: {student_id}")
#
#         student = db.query(Students).filter(Students.id == student_id).first()
#         if not student:
#             raise HTTPException(status_code=404, detail="Ученик не найден")
#
#         # Функция для безопасного преобразования
#         def parse_value(value):
#             if value is None or value == "":
#                 return None
#             return value
#
#         def parse_int(value):
#             if value is None or value == "":
#                 return None
#             try:
#                 return int(value)
#             except (ValueError, TypeError):
#                 return None
#
#         def parse_bool(value):
#             return value == "on"
#
#         # Обновляем поля
#         student.name = name
#         student.birthday = datetime.fromisoformat(birthday) if birthday else None
#         student.sport_discipline = parse_int(sport_discipline)
#         student.rang = parse_value(rang)
#         student.sports_rank = parse_int(sports_rank)
#         student.sex = parse_value(sex)
#         student.weight = parse_int(weight)
#         student.head_trainer_id = parse_int(head_trainer_id)
#         student.second_trainer_id = parse_int(second_trainer_id)
#         student.price = parse_int(price)
#         student.payment_day = parse_int(payment_day)
#         student.classes_remaining = parse_int(classes_remaining)
#         student.expected_payment_date = datetime.fromisoformat(
#             expected_payment_date).date() if expected_payment_date else None
#         student.telephone = parse_value(telephone)
#         student.parent1 = parse_int(parent1)
#         student.parent2 = parse_int(parent2)
#         student.date_start = datetime.fromisoformat(date_start) if date_start else None
#         student.telegram_id = parse_int(telegram_id)
#         student.active = parse_bool(active)
#
#         db.commit()
#
#         return JSONResponse({"status": "success", "message": "Данные ученика успешно обновлены"})
#
#     except Exception as e:
#         db.rollback()
#         logger.error(f"Ошибка при сохранении: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Ошибка обновления: {str(e)}")


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


@router.get("/edit-students/get-medical-certificates/{student_id}")
async def get_medical_certificates(student_id: int, db: Session = Depends(get_db)):
    """Получение медицинских справок ученика"""
    try:
        print(f"🔹 Запрос медицинских справок ученика ID: {student_id}")

        # Получаем активные справки ученика
        certificates = db.query(MedCertificat_received).filter(
            and_(
                MedCertificat_received.student_id == student_id,
                MedCertificat_received.active == True
            )
        ).all()

        result = []
        for cert in certificates:
            # Получаем информацию о типе справки
            cert_type = db.query(MedCertificat_type).filter(
                MedCertificat_type.id == cert.cert_id
            ).first()

            result.append({
                "id": cert.id,
                "cert_id": cert.cert_id,
                "cert_name": cert_type.name_cert if cert_type else "Неизвестная справка",
                "date_start": cert.date_start.isoformat() if cert.date_start else None,
                "date_end": cert.date_end.isoformat() if cert.date_end else None,
                "active": cert.active
            })

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"❌ Ошибка загрузки медицинских справок: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки справок: {str(e)}")


@router.get("/edit-students/get-certificate-types")
async def get_certificate_types(db: Session = Depends(get_db)):
    """Получение списка типов медицинских справок"""
    try:
        cert_types = db.query(MedCertificat_type).all()

        result = [{"id": cert.id, "name": cert.name_cert} for cert in cert_types]
        return JSONResponse(result)

    except Exception as e:
        logger.error(f"❌ Ошибка загрузки типов справок: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки типов справок: {str(e)}")


@router.post("/edit-students/update-medical-certificate")
async def update_medical_certificate(
        request: Request,
        db: Session = Depends(get_db)
):
    """Обновление медицинской справки"""
    try:
        # Получаем данные формы
        form_data = await request.form()
        print("🔹 Получены данные формы для обновления справки:")
        for key, value in form_data.items():
            print(f"  {key}: {value} (тип: {type(value)})")

        # Извлекаем данные с преобразованием типов
        certificate_id = int(form_data.get('certificate_id')) if form_data.get('certificate_id') else None
        student_id = int(form_data.get('student_id')) if form_data.get('student_id') else None
        cert_id = int(form_data.get('cert_id')) if form_data.get('cert_id') else None
        date_start = form_data.get('date_start')
        date_end = form_data.get('date_end')
        active = form_data.get('active')

        if not certificate_id:
            raise HTTPException(status_code=400, detail="ID справки обязательно")

        certificate = db.query(MedCertificat_received).filter(
            MedCertificat_received.id == certificate_id
        ).first()

        if not certificate:
            raise HTTPException(status_code=404, detail="Справка не найдена")

        # Обновляем поля
        if cert_id:
            certificate.cert_id = cert_id
        if date_start:
            certificate.date_start = datetime.fromisoformat(date_start).date()
        if date_end:
            certificate.date_end = datetime.fromisoformat(date_end).date()
        if active is not None:
            certificate.active = active == "on"

        db.commit()

        return JSONResponse({
            "status": "success",
            "message": "Справка успешно обновлена"
        })

    except ValueError as e:
        db.rollback()
        logger.error(f"❌ Ошибка преобразования типов: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Ошибка в данных: {str(e)}")
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Ошибка при обновлении справки: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ошибка обновления справки: {str(e)}")


@router.post("/edit-students/add-medical-certificate")
async def add_medical_certificate(
        request: Request,
        db: Session = Depends(get_db)
):
    """Добавление новой медицинской справки"""
    try:
        # Получаем данные формы
        form_data = await request.form()
        print("🔹 Получены данные формы для добавления справки:")
        for key, value in form_data.items():
            print(f"  {key}: {value} (тип: {type(value)})")

        # Извлекаем данные с преобразованием типов
        student_id = int(form_data.get('student_id')) if form_data.get('student_id') else None
        cert_id = int(form_data.get('cert_id')) if form_data.get('cert_id') else None
        date_start = form_data.get('date_start')
        date_end = form_data.get('date_end')
        active = form_data.get('active')

        if not student_id:
            raise HTTPException(status_code=400, detail="ID ученика обязательно")
        if not cert_id:
            raise HTTPException(status_code=400, detail="Тип справки обязателен")
        if not date_start:
            raise HTTPException(status_code=400, detail="Дата начала обязательна")
        if not date_end:
            raise HTTPException(status_code=400, detail="Дата окончания обязательна")

        # Проверяем существование ученика
        student = db.query(Students).filter(Students.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Ученик не найден")

        # Проверяем существование типа справки
        cert_type = db.query(MedCertificat_type).filter(MedCertificat_type.id == cert_id).first()
        if not cert_type:
            raise HTTPException(status_code=404, detail="Тип справки не найден")

        # Создаем новую справку
        new_cert = MedCertificat_received(
            student_id=student_id,
            cert_id=cert_id,
            date_start=datetime.fromisoformat(date_start).date(),
            date_end=datetime.fromisoformat(date_end).date(),
            active=active == "on" if active else True
        )

        db.add(new_cert)
        db.commit()
        db.refresh(new_cert)

        logger.info(f"✅ Добавлена справка для ученика {student.name}, тип: {cert_type.name_cert}")

        return JSONResponse({
            "status": "success",
            "message": "Справка успешно добавлена",
            "certificate_id": new_cert.id
        })

    except ValueError as e:
        db.rollback()
        logger.error(f"❌ Ошибка преобразования типов: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Ошибка в данных: {str(e)}")
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Ошибка при добавлении справки: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ошибка добавления справки: {str(e)}")


@router.delete("/edit-students/delete-medical-certificate/{certificate_id}")
async def delete_medical_certificate(certificate_id: int, db: Session = Depends(get_db)):
    """Удаление медицинской справки"""
    try:
        print(f"🔹 Удаление справки ID: {certificate_id}")

        certificate = db.query(MedCertificat_received).filter(
            MedCertificat_received.id == certificate_id
        ).first()

        if not certificate:
            raise HTTPException(status_code=404, detail="Справка не найдена")

        db.delete(certificate)
        db.commit()

        return JSONResponse({
            "status": "success",
            "message": "Справка успешно удалена"
        })

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Ошибка при удалении справки: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка удаления справки: {str(e)}")


# -------------------------------------------------------НАГРАДЫ-------------------------------------------------------

@router.get("/edit-students/get-awards/{student_id}")
async def get_awards(student_id: int, db: Session = Depends(get_db)):
    """Получение наград и результатов соревнований ученика"""
    try:
        print(f"🔹 Запрос наград ученика ID: {student_id}")

        # Получаем записи о соревнованиях ученика
        awards = db.query(Competition_student).filter(
            Competition_student.student_id == student_id
        ).all()

        result = []
        for award in awards:
            # Получаем информацию о соревновании
            competition = db.query(Сompetition).filter(
                Сompetition.id == award.competition_id
            ).first()

            result.append({
                "id": award.id,
                "competition_id": award.competition_id,
                "competition_name": competition.name if competition else "Неизвестное соревнование",
                "competition_date": competition.date.isoformat() if competition and competition.date else None,
                "status_id": award.status_id
            })

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"❌ Ошибка загрузки наград: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки наград: {str(e)}")


@router.get("/edit-students/get-competitions")
async def get_competitions(db: Session = Depends(get_db)):
    """Получение списка всех соревнований"""
    try:
        competitions = db.query(Сompetition).all()

        result = [{"id": comp.id, "name": comp.name, "date": comp.date.isoformat() if comp.date else None}
                 for comp in competitions]
        return JSONResponse(result)

    except Exception as e:
        logger.error(f"❌ Ошибка загрузки соревнований: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки соревнований: {str(e)}")


@router.post("/edit-students/update-award")
async def update_award(
        request: Request,
        db: Session = Depends(get_db)
):
    """Обновление результата соревнования"""
    try:
        # Получаем данные формы
        form_data = await request.form()
        print("🔹 Получены данные формы для обновления награды:")
        for key, value in form_data.items():
            print(f"  {key}: {value} (тип: {type(value)})")

        # Извлекаем данные с преобразованием типов
        award_id = int(form_data.get('award_id')) if form_data.get('award_id') else None
        student_id = int(form_data.get('student_id')) if form_data.get('student_id') else None
        competition_id = int(form_data.get('competition_id')) if form_data.get('competition_id') else None
        status_id = int(form_data.get('status_id')) if form_data.get('status_id') else None

        if not award_id:
            raise HTTPException(status_code=400, detail="ID записи обязательно")

        award = db.query(Competition_student).filter(
            Competition_student.id == award_id
        ).first()

        if not award:
            raise HTTPException(status_code=404, detail="Запись не найдена")

        # Обновляем статус
        if status_id is not None:
            award.status_id = status_id

        db.commit()

        return JSONResponse({
            "status": "success",
            "message": "Результат успешно обновлен"
        })

    except ValueError as e:
        db.rollback()
        logger.error(f"❌ Ошибка преобразования типов: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Ошибка в данных: {str(e)}")
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Ошибка при обновлении результата: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ошибка обновления результата: {str(e)}")


@router.post("/edit-students/add-award")
async def add_award(
        request: Request,
        db: Session = Depends(get_db)
):
    """Добавление новой записи о соревновании"""
    try:
        # Получаем данные формы
        form_data = await request.form()
        print("🔹 Получены данные формы для добавления награды:")
        for key, value in form_data.items():
            print(f"  {key}: {value} (тип: {type(value)})")

        # Извлекаем данные с преобразованием типов
        student_id = int(form_data.get('student_id')) if form_data.get('student_id') else None
        competition_id = int(form_data.get('competition_id')) if form_data.get('competition_id') else None
        status_id = int(form_data.get('status_id')) if form_data.get('status_id') else 0

        if not student_id:
            raise HTTPException(status_code=400, detail="ID ученика обязательно")
        if not competition_id:
            raise HTTPException(status_code=400, detail="Соревнование обязательно")
        if status_id is None:
            status_id = 0  # По умолчанию "Ожидание"

        # Проверяем существование ученика
        student = db.query(Students).filter(Students.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Ученик не найден")

        # Проверяем существование соревнования
        competition = db.query(Сompetition).filter(Сompetition.id == competition_id).first()
        if not competition:
            raise HTTPException(status_code=404, detail="Соревнование не найдено")

        # Проверяем, не существует ли уже запись для этого ученика и соревнования
        existing_award = db.query(Competition_student).filter(
            and_(
                Competition_student.student_id == student_id,
                Competition_student.competition_id == competition_id
            )
        ).first()

        if existing_award:
            raise HTTPException(status_code=400, detail="Запись для этого соревнования уже существует")

        # Создаем новую запись
        new_award = Competition_student(
            student_id=student_id,
            competition_id=competition_id,
            status_id=status_id
        )

        db.add(new_award)
        db.commit()
        db.refresh(new_award)

        logger.info(f"✅ Добавлена запись о соревновании для ученика {student.name}, соревнование: {competition.name}")

        return JSONResponse({
            "status": "success",
            "message": "Запись успешно добавлена",
            "award_id": new_award.id
        })

    except ValueError as e:
        db.rollback()
        logger.error(f"❌ Ошибка преобразования типов: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Ошибка в данных: {str(e)}")
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Ошибка при добавлении записи: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ошибка добавления записи: {str(e)}")


@router.delete("/edit-students/delete-award/{award_id}")
async def delete_award(award_id: int, db: Session = Depends(get_db)):
    """Удаление записи о соревновании"""
    try:
        print(f"🔹 Удаление записи о соревновании ID: {award_id}")

        award = db.query(Competition_student).filter(
            Competition_student.id == award_id
        ).first()

        if not award:
            raise HTTPException(status_code=404, detail="Запись не найдена")

        db.delete(award)
        db.commit()

        return JSONResponse({
            "status": "success",
            "message": "Запись успешно удалена"
        })

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Ошибка при удалении записи: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка удаления записи: {str(e)}")


# ----------------Родители---------------------

@router.get("/edit-students/get-parents/{student_id}")
async def get_student_parents(student_id: int, db: Session = Depends(get_db)):
    """Получение списка родителей ученика"""
    try:
        print(f"🔹 Запрос родителей ученика ID: {student_id}")

        # Получаем связи ученик-родители
        parent_relations = db.query(Students_parents).filter(
            Students_parents.student == student_id
        ).all()

        result = []
        for relation in parent_relations:
            # Получаем информацию о родителе из Tg_notif_user
            parent = db.query(Tg_notif_user).filter(
                Tg_notif_user.id == relation.parents
            ).first()

            if parent:
                result.append({
                    "id": parent.id,
                    "relation_id": relation.id,
                    "telegram_id": parent.telegram_id,
                    "full_name": parent.full_name or "",
                    "telegram_username": parent.telegram_username or "",
                    "phone": parent.phone or "",
                    "email": parent.email or "",
                    "get_info_student": parent.get_info_student
                })

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"❌ Ошибка загрузки родителей: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки родителей: {str(e)}")


@router.get("/edit-students/search-parents")
async def search_parents(query: str, db: Session = Depends(get_db)):
    """Поиск родителей для автозаполнения"""
    try:
        if not query or len(query) < 2:
            return JSONResponse([])

        # Ищем родителей по различным полям
        parents = db.query(Tg_notif_user).filter(
            and_(
                Tg_notif_user.is_active == True,
                or_(
                    Tg_notif_user.full_name.ilike(f"%{query}%"),
                    Tg_notif_user.telegram_username.ilike(f"%{query}%"),
                    Tg_notif_user.phone.ilike(f"%{query}%"),
                    Tg_notif_user.email.ilike(f"%{query}%")
                )
            )
        ).limit(10).all()

        result = [
            {
                "id": parent.id,
                "full_name": parent.full_name or "",
                "telegram_username": parent.telegram_username or "",
                "phone": parent.phone or "",
                "email": parent.email or ""
            }
            for parent in parents
        ]

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"❌ Ошибка поиска родителей: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка поиска родителей: {str(e)}")


@router.post("/edit-students/add-parent")
async def add_parent(
        student_id: int = Form(...),
        parent_id: int = Form(...),
        db: Session = Depends(get_db)
):
    """Добавление родителя к ученику"""
    try:
        # Проверяем существование ученика
        student = db.query(Students).filter(Students.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Ученик не найден")

        # Проверяем существование родителя
        parent = db.query(Tg_notif_user).filter(Tg_notif_user.id == parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Родитель не найден")

        # Проверяем, не существует ли уже связь
        existing_relation = db.query(Students_parents).filter(
            and_(
                Students_parents.student == student_id,
                Students_parents.parents == parent_id
            )
        ).first()

        if existing_relation:
            raise HTTPException(status_code=400, detail="Родитель уже добавлен к ученику")

        # Создаем новую связь
        new_relation = Students_parents(
            student=student_id,
            parents=parent_id
        )

        db.add(new_relation)
        db.commit()
        db.refresh(new_relation)

        logger.info(f"✅ Добавлен родитель {parent.full_name} к ученику {student.name}")

        return JSONResponse({
            "status": "success",
            "message": "Родитель успешно добавлен",
            "relation_id": new_relation.id
        })

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Ошибка при добавлении родителя: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка добавления родителя: {str(e)}")


@router.delete("/edit-students/remove-parent/{relation_id}")
async def remove_parent(relation_id: int, db: Session = Depends(get_db)):
    """Удаление связи с родителем"""
    try:
        print(f"🔹 Удаление связи с родителем ID: {relation_id}")

        relation = db.query(Students_parents).filter(
            Students_parents.id == relation_id
        ).first()

        if not relation:
            raise HTTPException(status_code=404, detail="Связь не найдена")

        db.delete(relation)
        db.commit()

        return JSONResponse({
            "status": "success",
            "message": "Родитель успешно удален из ученика"
        })

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Ошибка при удалении связи: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка удаления связи: {str(e)}")


# ----------------Оплаты---------------------
# api/students.py - добавьте этот endpoint

@router.post("/api/student/{student_id}/process-payment")
async def process_student_payment(
        student_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db_async)
):
    """Обработка оплаты для ученика через веб-интерфейс"""
    try:
        # Проверяем авторизацию пользователя
        user_info = getattr(request.state, 'user', None)
        if not user_info or not user_info.get("authenticated"):
            raise HTTPException(status_code=401, detail="Не авторизован")

        # Получаем данные из запроса
        data = await request.json()
        amount = int(data.get('amount', 0))

        if amount <= 0:
            raise HTTPException(status_code=400, detail="Сумма должна быть больше 0")

        # Используем асинхронную функцию из db_funk.py
        from db_handler.db_funk import process_payment_via_web
        result = await process_payment_via_web(student_id, amount)

        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "new_balance": result["new_balance"],
                "classes_added": result["classes_added"],
                "next_payment_date": result["next_payment_date"],
                "student_name": result["student_name"],
                "price_description": result["price_description"]
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])

    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат суммы")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing payment: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


# api/students.py - добавьте этот endpoint

@router.post("/api/student/{student_id}/update-balance")
async def update_student_balance(
        student_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db_async)
):
    """Обновление баланса ученика с сохранением логов"""
    try:
        # Проверяем авторизацию
        user_info = getattr(request.state, 'user', None)
        if not user_info or not user_info.get("authenticated"):
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Не авторизован"}
            )

        user_id = user_info.get("user_id")  # ID пользователя из middleware

        # Получаем данные
        try:
            data = await request.json()
        except:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Неверный формат JSON"}
            )

        new_balance = data.get('new_balance')
        reason = data.get('reason', 'Ручная корректировка')

        if new_balance is None:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Не указан новый баланс"}
            )

        # Преобразуем в число
        try:
            new_balance = int(new_balance)
        except (ValueError, TypeError):
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Баланс должен быть числом"}
            )

        if new_balance < 0:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Баланс не может быть отрицательным"}
            )

        # Получаем ученика
        from database.models import Students
        student = await db.execute(
            select(Students).filter(Students.id == student_id)
        )
        student = student.scalar_one_or_none()

        if not student:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Ученик не найден"}
            )

        old_balance = student.classes_remaining or 0
        difference = new_balance - old_balance

        # Сохраняем в лог
        from database.models import BalanceLog
        balance_log = BalanceLog(
            student_id=student_id,
            old_balance=old_balance,
            new_balance=new_balance,
            difference=difference,
            reason=reason,
            changed_by=user_id or 0  # 0 если пользователь не определен
        )
        db.add(balance_log)

        # Обновляем баланс
        student.classes_remaining = new_balance

        # Если разница большая, обновляем дату оплаты
        from datetime import datetime, timedelta
        from math import ceil

        if abs(difference) > 5:
            # Получаем количество дней тренировок в неделю
            from database.models import Students_schedule, Schedule
            schedule_count = await db.execute(
                select(func.count(distinct(Students_schedule.schedule)))
                .join(Schedule, Students_schedule.schedule == Schedule.id)
                .filter(Students_schedule.student == student_id)
            )
            days_per_week = schedule_count.scalar() or 1

            if days_per_week > 0 and new_balance > 0:
                weeks_remaining = new_balance / days_per_week
                if weeks_remaining < 1:
                    weeks_remaining = 1
                else:
                    weeks_remaining = ceil(weeks_remaining)

                new_payment_date = datetime.now().date() + timedelta(days=weeks_remaining * 7 + 3)
                student.expected_payment_date = new_payment_date
                payment_date_info = f"Дата оплаты обновлена: {new_payment_date.strftime('%d.%m.%Y')}"
            else:
                payment_date_info = "Дата оплаты не изменилась"
        else:
            payment_date_info = ""

        await db.commit()

        difference_text = f"({difference:+d})" if difference != 0 else ""

        return {
            "success": True,
            "message": f"Баланс обновлен: {old_balance} → {new_balance} {difference_text}",
            "old_balance": old_balance,
            "new_balance": new_balance,
            "difference": difference,
            "reason": reason,
            "payment_date_info": payment_date_info,
            "student_name": student.name,
            "log_id": balance_log.id
        }

    except Exception as e:
        print(f"Error updating balance: {str(e)}")
        try:
            await db.rollback()
        except:
            pass
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Внутренняя ошибка сервера: {str(e)}"}
        )


# api/students.py - endpoint для получения логов
@router.get("/api/student/{student_id}/balance-history")
async def get_balance_history(
        student_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db_async)
):
    """Получение истории изменений баланса ученика"""
    try:
        # Проверяем авторизацию
        user_info = getattr(request.state, 'user', None)
        if not user_info or not user_info.get("authenticated"):
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Не авторизован"}
            )

        from database.models import BalanceLog

        # Получаем логи
        logs = await db.execute(
            select(BalanceLog)
            .filter(BalanceLog.student_id == student_id)
            .order_by(BalanceLog.changed_at.desc())
            .limit(50)
        )
        logs_list = logs.scalars().all()

        # Форматируем ответ
        history = []
        for log in logs_list:
            history.append({
                "id": log.id,
                "old_balance": log.old_balance,
                "new_balance": log.new_balance,
                "difference": log.difference,
                "reason": log.reason or "Не указана",
                "changed_at": log.changed_at.strftime("%d.%m.%Y %H:%M"),
                "changed_by": log.changed_by
            })

        return {
            "success": True,
            "student_id": student_id,
            "history": history,
            "total": len(history)
        }

    except Exception as e:
        print(f"Error getting balance history: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/api/prices")
async def get_prices(
        request: Request,
        db: AsyncSession = Depends(get_db_async)
):
    """Получение списка всех тарифов"""
    try:
        # Проверяем авторизацию
        user_info = getattr(request.state, 'user', None)
        if not user_info or not user_info.get("authenticated"):
            raise HTTPException(status_code=401, detail="Не авторизован")

        # Получаем список тарифов
        prices = await db.execute(
            select(models.Prices).order_by(models.Prices.price)
        )
        price_list = prices.scalars().all()

        return [
            {
                "id": p.id,
                "price": p.price,
                "classes_in_price": p.classes_in_price,
                "description": p.description or f"Тариф {p.id}"
            }
            for p in price_list
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


#  __________________Справки_поБОлезням_______________________________________

@router.post("/api/student/{student_id}/medical-certificate")
async def add_medical_certificate(
        student_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db_async)
):
    """Добавление справки по болезни"""
    try:
        # Проверяем авторизацию
        user_info = getattr(request.state, 'user', None)
        if not user_info or not user_info.get("authenticated"):
            raise HTTPException(status_code=401, detail="Не авторизован")

        data = await request.json()
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="Не указаны даты")

        # Используем функцию из db_funk.py
        from db_handler.db_funk import process_medical_certificate
        result = await process_medical_certificate(student_id, start_date, end_date)

        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "new_balance": result["new_balance"],
                "missed_classes": result["missed_classes"],
                "start_date": result["start_date"],
                "end_date": result["end_date"]
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding medical certificate: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get("/api/student/{student_id}/medical-certificates")
async def get_medical_certificates(
        student_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db_async)
):
    """Получение списка справок по болезни ученика"""
    try:
        # Проверяем авторизацию
        user_info = getattr(request.state, 'user', None)
        if not user_info or not user_info.get("authenticated"):
            raise HTTPException(status_code=401, detail="Не авторизован")

        from db_handler.db_funk import get_student_medical_certificates
        certificates = await get_student_medical_certificates(student_id)

        return {
            "success": True,
            "certificates": certificates
        }

    except Exception as e:
        logger.error(f"Error getting medical certificates: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.delete("/api/student/{student_id}/medical-certificate/{certificate_id}")
async def delete_medical_certificate_endpoint(
        student_id: int,
        certificate_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db_async)
):
    """Удаление справки по болезни"""
    try:
        # Проверяем авторизацию
        user_info = getattr(request.state, 'user', None)
        if not user_info or not user_info.get("authenticated"):
            raise HTTPException(status_code=401, detail="Не авторизован")

        from db_handler.db_funk import delete_medical_certificate
        result = await delete_medical_certificate(certificate_id, student_id)

        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "new_balance": result["new_balance"],
                "classes_removed": result["classes_removed"]
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting medical certificate: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")