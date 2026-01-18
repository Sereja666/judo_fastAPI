
from math import ceil
from config import settings
from datetime import datetime, timedelta
from logger_config import logger
import asyncpg

from database.models import schema



# функция, для получения информации по конкретному пользователю
async def get_user_data(user_id: int, table_name=f'{schema}.telegram_user'):
    conn = await asyncpg.connect(**settings.db.pg_link)
    try:
        logger.info(f'пытаюсь получить инфу о {user_id}')
        row = await conn.fetchrow(
            f"SELECT * FROM {table_name} WHERE telegram_id = $1",
            user_id
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def get_all_users(table_name='student', schema_name=schema, count=False):
    conn = await asyncpg.connect(**settings.db.pg_link)
    try:
        # Формируем полное имя таблицы с учетом схемы
        full_table_name = f"{schema_name}.{table_name}" if schema_name else table_name

        if count:
            # Запрос для получения количества записей
            query = f"SELECT COUNT(*) FROM {full_table_name}"
            result = await conn.fetchval(query)
            return result
        else:
            # Запрос для получения всех данных
            query = f"SELECT * FROM {full_table_name}"
            rows = await conn.fetch(query)
            return [dict(row) for row in rows]
    finally:
        await conn.close()


async def insert_user(user_data: dict, table_name: str = f'{schema}.telegram_user'):
    conn = await asyncpg.connect(**settings.db.pg_link)
    try:
        # Подготавливаем SQL-запрос
        columns = ', '.join(user_data.keys())
        placeholders = ', '.join([f'${i + 1}' for i in range(len(user_data))])

        query = f"""
        INSERT INTO {table_name} ({columns})
        VALUES ({placeholders})
        RETURNING *
        """

        # Выполняем запрос
        row = await conn.fetchrow(query, *user_data.values())
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error inserting user: {e}")
        return None
    finally:
        await conn.close()


async def get_user_permissions(user_telegram_id: int) -> int:
    """
    Получает права пользователя из базы данных
    Возвращает permissions или 0 (гость) если пользователь не найден
    """
    try:
        result = await execute_raw_sql(
            f"SELECT permissions FROM {schema}.telegram_user WHERE telegram_id = $1;",
            user_telegram_id
        )
        if result:
            return result[0]['permissions']
        else:
            return 0  # Гость по умолчанию
    except Exception as e:
        logger.error(f"Error getting user permissions: {str(e)}")
        return 0  # Гость в случае ошибки



async def execute_raw_sql(query: str, *params):
    """Выполняет SQL запрос с параметрами и возвращает результат"""
    conn = await asyncpg.connect(**settings.db.pg_link)
    try:
        if params:
            result = await conn.fetch(query, *params)
        else:
            result = await conn.fetch(query)
        return result
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        raise  # Пробрасываем исключение дальше
    finally:
        await conn.close()


async def save_selection(schedule_id: int, student_ids: list, trainer_id: int, place_id: int, discipline_id: int):
    """
    Сохраняет посещения студентов в таблицу public.visit
    Каждый студент - отдельная запись с новым ID
    :param schedule_id: ID расписания (shedule)
    :param student_ids: Список ID студентов
    :param trainer_id: ID тренера
    :param place_id: ID места тренировки
    :param discipline_id: ID спортивной дисциплины
    :return: Tuple (success: bool, message: str)
    """
    try:
        if not student_ids:
            return False, "Нет студентов для сохранения"

        # Получаем данные о расписании (дату и время)
        schedule_data = await execute_raw_sql(
            f"SELECT date, time_start FROM {schema}.schedule WHERE id = {schedule_id};"
        )

        if not schedule_data:
            return False, "Расписание не найдено"

        # Формируем дату и время посещения
        visit_datetime = f"{schedule_data[0]['date']} {schedule_data[0]['time_start']}"

        # Проверяем существование студентов
        existing_students = await execute_raw_sql(
            f"SELECT id FROM {schema}.student WHERE id IN ({','.join(map(str, student_ids))});"
        )
        existing_ids = [s['id'] for s in existing_students]
        missing_ids = set(student_ids) - set(existing_ids)

        success_count = 0
        errors = []

        # Для каждого студента создаем отдельную запись
        for student_id in existing_ids:
            try:
                # Проверяем, не записан ли уже студент на это занятие
                existing_visit = await execute_raw_sql(
                    f"SELECT id FROM {schema}.visit "
                    f"WHERE shedule = {schedule_id} AND student = {student_id};"
                )

                if existing_visit:
                    # Обновляем существующую запись
                    await execute_raw_sql(
                        f"UPDATE {schema}.visit SET "
                        f"data = '{visit_datetime}', "
                        f"trainer = {trainer_id}, "
                        f"place = {place_id}, "
                        f"sport_discipline = {discipline_id}, "
                        f"updated_at = NOW() "
                        f"WHERE id = {existing_visit[0]['id']};"
                    )
                else:
                    # Создаем новую запись
                    await execute_raw_sql(
                        f"INSERT INTO {schema}.visit "
                        f"(data, trainer, student, place, sport_discipline, shedule) "
                        f"VALUES ("
                        f"'{visit_datetime}', "
                        f"{trainer_id}, "
                        f"{student_id}, "
                        f"{place_id}, "
                        f"{discipline_id}, "
                        f"{schedule_id}"
                        f");"
                    )
                success_count += 1
            except Exception as e:
                errors.append(f"Студент {student_id}: {str(e)}")
                logger.error(f"Ошибка при сохранении для студента {student_id}: {e}")

        # Формируем итоговое сообщение
        message_parts = []
        if success_count:
            message_parts.append(f"Успешно: {success_count}/{len(student_ids)}")
        if missing_ids:
            message_parts.append(f"Не найдены студенты: {len(missing_ids)}")
        if errors:
            message_parts.append(f"Ошибок: {len(errors)}")

        return bool(success_count), "; ".join(message_parts)

    except Exception as e:
        logger.error(f"Ошибка в save_selection: {e}")
        return False, f"Системная ошибка: {str(e)}"


async def process_payment(student_name: str, amount: int) -> dict:
    """
    Обрабатывает оплату для ученика
    Возвращает словарь с результатом операции
    """
    try:
        # Улучшенный поиск ученика - ищем по разным вариантам имени
        student_data = await execute_raw_sql(
            f"""SELECT id, name, classes_remaining, price 
            FROM public.student 
            WHERE active = true 
            AND (
                name ILIKE $1 
                OR name ILIKE $2
                OR name ILIKE $3
                OR $4 ILIKE '%' || split_part(name, ' ', 1) || '%'
                OR $4 ILIKE '%' || split_part(name, ' ', 1) || ' ' || split_part(name, ' ', 2) || '%'
            )
            ORDER BY 
                CASE 
                    WHEN name ILIKE $1 THEN 1
                    WHEN name ILIKE $2 THEN 2
                    WHEN name ILIKE $3 THEN 3
                    ELSE 4
                END
            LIMIT 1;""",
            student_name,
            f"{student_name}%",
            f"%{student_name}%",
            student_name
        )

        if not student_data:
            # Try to find by surname and name (first two words)
            name_parts = student_name.split()
            if len(name_parts) >= 2:
                surname_name = f"{name_parts[0]} {name_parts[1]}"
                student_data = await execute_raw_sql(
                    f"""SELECT id, name, classes_remaining, price 
                    FROM public.student 
                    WHERE active = true 
                    AND name ILIKE $1
                    LIMIT 1;""",
                    f"{surname_name}%"
                )

        if not student_data:
            return {"success": False, "error": f"Ученик '{student_name}' не найден"}

        student = student_data[0]
        student_id = student['id']
        old_price_id = student['price']  # Теперь это ID тарифа, а не сумма

        # Ищем цену в таблице price
        price_data = await execute_raw_sql(
            f"SELECT id, price, classes_in_price, description FROM public.price WHERE price = $1;",
            amount
        )

        if not price_data:
            return {"success": False, "error": f"Тариф с суммой {amount} руб. не найден"}

        price = price_data[0]
        price_id = price['id']
        classes_to_add = price['classes_in_price']

        # Получаем информацию о старом тарифе для сравнения
        old_price_info = None
        if old_price_id:
            old_price_data = await execute_raw_sql(
                f"SELECT price, description FROM public.price WHERE id = $1;",
                old_price_id
            )
            if old_price_data:
                old_price_info = old_price_data[0]

        # Проверяем и устанавливаем значения по умолчанию
        current_balance = student['classes_remaining'] if student['classes_remaining'] is not None else 0
        classes_to_add = classes_to_add if classes_to_add is not None else 0

        # Рассчитываем новую дату оплаты
        from datetime import datetime, timedelta
        
        # Получаем расписание студента для расчета дней в неделю
        schedule_data = await execute_raw_sql(
            f"""SELECT COUNT(DISTINCT ss.schedule) as training_days_per_week
            FROM {schema}.student_schedule ss
            JOIN {schema}.schedule sched ON ss.schedule = sched.id
            WHERE ss.student = $1""",
            student_id
        )
        
        days_per_week = schedule_data[0]['training_days_per_week'] if schedule_data and schedule_data[0]['training_days_per_week'] else 1
        
        # Рассчитываем, на сколько недель хватит нового баланса
        new_balance = current_balance + classes_to_add
        
        if days_per_week > 0 and new_balance > 0:
            # Рассчитываем количество недель, на которое хватит занятий
            weeks_remaining = new_balance / days_per_week
            
            # Если студент ходит реже, чем 1 раз в неделю, берем минимум 1 неделю
            if weeks_remaining < 1:
                weeks_remaining = 1
            else:
                weeks_remaining = ceil(weeks_remaining)
            
            # Устанавливаем дату оплаты через рассчитанное количество недель + буфер 3 дня
            new_payment_date = datetime.now().date() + timedelta(days=weeks_remaining * 7 + 3)
        else:
            # Если нет расписания или нулевой баланс - ставим дату через 30 дней
            new_payment_date = datetime.now().date() + timedelta(days=30)

        # Начинаем транзакцию
        # 1. Добавляем запись в payment
        payment_result = await execute_raw_sql(
            f"""INSERT INTO public.payment 
                (student_id, price_id, payment_amount, payment_date) 
            VALUES ($1, $2, $3, CURRENT_DATE) 
            RETURNING id;""",
            student_id, price_id, amount
        )

        if not payment_result:
            return {"success": False, "error": "Ошибка при записи платежа"}

        # 2. Обновляем баланс занятий, price_id и дату оплаты у ученика
        update_result = await execute_raw_sql(
            f"UPDATE public.student SET classes_remaining = $1, price = $2, expected_payment_date = $3 WHERE id = $4;",
            new_balance, price_id, new_payment_date, student_id
        )

        # Получаем текущую дату для ответа
        current_date_data = await execute_raw_sql(f"SELECT CURRENT_DATE as today;")
        payment_date = current_date_data[0]['today'].strftime("%d.%m.%Y") if current_date_data else "сегодня"

        # Формируем информацию об изменении тарифа
        price_change_info = ""
        if old_price_info and old_price_id != price_id:
            price_change_info = f"\n💰 Изменен тариф: <b>{old_price_info['description']} ({old_price_info['price']} руб.) → {price['description']} ({price['price']} руб.)</b>"
        elif old_price_id == price_id:
            price_change_info = f"\n💰 Тариф остался прежним: <b>{price['description']} ({price['price']} руб.)</b>"
        else:
            price_change_info = f"\n💰 Установлен тариф: <b>{price['description']} ({price['price']} руб.)</b>"

        # Добавляем информацию о дате оплаты
        payment_date_info = f"\n📅 Следующая оплата: <b>{new_payment_date.strftime('%d.%m.%Y')}</b>"

        return {
            "success": True,
            "student_name": student['name'],
            "amount": amount,
            "price_description": price['description'],
            "classes_added": classes_to_add,
            "new_balance": new_balance,
            "payment_date": payment_date,
            "next_payment_date": new_payment_date.strftime("%d.%m.%Y"),
            "old_price": old_price_info['price'] if old_price_info else None,
            "new_price": price['price'],
            "price_change_info": price_change_info,
            "payment_date_info": payment_date_info
        }

    except Exception as e:
        logger.error(f"Error processing payment: {str(e)}")
        return {"success": False, "error": f"Системная ошибка: {str(e)}"}


async def get_all_certificates():
    """Получает все медицинские справки"""
    query = """
    SELECT 
        s.name as student_name,
        mt.name_cert as certificate_type,
        TO_CHAR(mr.date_start, 'DD.MM.YYYY') as start_date,
        TO_CHAR(mr.date_end, 'DD.MM.YYYY') as end_date,
        CASE 
            WHEN mr.active = true AND mr.date_end >= CURRENT_DATE THEN 'active'
            WHEN mr.active = true AND mr.date_end < CURRENT_DATE THEN 'expired'
            ELSE 'inactive'
        END as status,
        mr.id as record_id
    FROM public.medcertificat_received mr
    JOIN public.student s ON mr.student_id = s.id
    JOIN public.medcertificat_type mt ON mr.cert_id = mt.id
    WHERE s.active = true
    ORDER BY s.name, mr.date_end DESC;
    """

    return await execute_raw_sql(query)


async def get_student_certificates(student_id: int):
    """Получает медицинские справки конкретного ученика"""
    query = """
    SELECT 
        mt.name_cert as certificate_type,
        TO_CHAR(mr.date_start, 'DD.MM.YYYY') as start_date,
        TO_CHAR(mr.date_end, 'DD.MM.YYYY') as end_date,
        CASE 
            WHEN mr.active = true AND mr.date_end >= CURRENT_DATE THEN 'active'
            WHEN mr.active = true AND mr.date_end < CURRENT_DATE THEN 'expired'
            ELSE 'inactive'
        END as status,
        CASE 
            WHEN mr.date_end >= CURRENT_DATE THEN 
                'Осталось ' || (mr.date_end - CURRENT_DATE) || ' дней'
            ELSE
                'Просрочена ' || (CURRENT_DATE - mr.date_end) || ' дней назад'
        END as days_info,
        mr.id as record_id
    FROM public.medcertificat_received mr
    JOIN public.medcertificat_type mt ON mr.cert_id = mt.id
    WHERE mr.student_id = $1
    ORDER BY mr.date_end DESC;
    """

    return await execute_raw_sql(query, student_id)



async def process_payment_via_web(student_id: int, amount: int) -> dict:
    """
    Обрабатывает оплату для ученика через веб-интерфейс
    Возвращает словарь с результатом операции
    """
    try:
        # Получаем информацию об ученике
        student_data = await execute_raw_sql(
            """SELECT id, name, classes_remaining, price 
            FROM public.student 
            WHERE id = $1 AND active = true;""",
            student_id
        )

        if not student_data:
            return {"success": False, "error": "Ученик не найден"}

        student = student_data[0]
        old_price_id = student['price']

        # Ищем цену в таблице price
        price_data = await execute_raw_sql(
            "SELECT id, price, classes_in_price, description FROM public.price WHERE price = $1;",
            amount
        )

        if not price_data:
            return {"success": False, "error": f"Тариф с суммой {amount} руб. не найден"}

        price = price_data[0]
        price_id = price['id']
        classes_to_add = price['classes_in_price'] or 0

        # Текущий баланс
        current_balance = student['classes_remaining'] if student['classes_remaining'] is not None else 0
        new_balance = current_balance + classes_to_add

        # Рассчитываем новую дату оплаты
        from datetime import datetime, timedelta
        from math import ceil

        # Получаем расписание студента
        schedule_data = await execute_raw_sql(
            """SELECT COUNT(DISTINCT ss.schedule) as training_days_per_week
            FROM public.student_schedule ss
            JOIN public.schedule sched ON ss.schedule = sched.id
            WHERE ss.student = $1""",
            student_id
        )

        days_per_week = schedule_data[0]['training_days_per_week'] if schedule_data and schedule_data[0][
            'training_days_per_week'] else 1

        # Рассчитываем дату следующей оплаты
        if days_per_week > 0 and new_balance > 0:
            weeks_remaining = new_balance / days_per_week
            if weeks_remaining < 1:
                weeks_remaining = 1
            else:
                weeks_remaining = ceil(weeks_remaining)

            new_payment_date = datetime.now().date() + timedelta(days=weeks_remaining * 7 + 3)
        else:
            new_payment_date = datetime.now().date() + timedelta(days=30)

        # Начинаем транзакцию
        # 1. Добавляем запись в payment
        payment_result = await execute_raw_sql(
            """INSERT INTO public.payment 
                (student_id, price_id, payment_amount, payment_date) 
            VALUES ($1, $2, $3, CURRENT_DATE) 
            RETURNING id;""",
            student_id, price_id, amount
        )

        if not payment_result:
            return {"success": False, "error": "Ошибка при записи платежа"}

        # 2. Обновляем баланс занятий, price_id и дату оплаты у ученика
        await execute_raw_sql(
            "UPDATE public.student SET classes_remaining = $1, price = $2, expected_payment_date = $3 WHERE id = $4;",
            new_balance, price_id, new_payment_date, student_id
        )

        # Получаем информацию о старом тарифе для сравнения
        old_price_info = None
        if old_price_id:
            old_price_data = await execute_raw_sql(
                "SELECT price, description FROM public.price WHERE id = $1;",
                old_price_id
            )
            if old_price_data:
                old_price_info = old_price_data[0]

        # Формируем информацию об изменении тарифа
        price_change_info = ""
        if old_price_info and old_price_id != price_id:
            price_change_info = f"Изменен тариф: {old_price_info['description']} ({old_price_info['price']} руб.) → {price['description']} ({price['price']} руб.)"
        elif old_price_id == price_id:
            price_change_info = f"Тариф остался прежним: {price['description']} ({price['price']} руб.)"
        else:
            price_change_info = f"Установлен тариф: {price['description']} ({price['price']} руб.)"

        return {
            "success": True,
            "student_name": student['name'],
            "amount": amount,
            "price_description": price['description'],
            "classes_added": classes_to_add,
            "new_balance": new_balance,
            "next_payment_date": new_payment_date.strftime("%d.%m.%Y"),
            "price_change_info": price_change_info,
            "message": f"Оплата успешно обработана! Добавлено {classes_to_add} занятий."
        }

    except Exception as e:
        logger.error(f"Error processing payment via web: {str(e)}")
        return {"success": False, "error": f"Системная ошибка: {str(e)}"}


# db_funk.py - добавьте эти функции

async def process_medical_certificate(student_id: int, start_date: str, end_date: str) -> dict:
    """
    Обрабатывает справку по болезни и возвращает пропущенные занятия
    Формат дат: 'DD.MM.YYYY'
    """
    try:

        # Преобразуем даты
        start_date_dt = datetime.strptime(start_date, '%d.%m.%Y').date()
        end_date_dt = datetime.strptime(end_date, '%d.%m.%Y').date()

        if start_date_dt > end_date_dt:
            return {"success": False, "error": "Дата начала не может быть позже даты окончания"}

        # Получаем информацию об ученике
        student_data = await execute_raw_sql(
            """SELECT id, name, classes_remaining 
            FROM public.student 
            WHERE id = $1 AND active = true;""",
            student_id
        )

        if not student_data:
            return {"success": False, "error": "Ученик не найден"}

        student = student_data[0]
        current_balance = student['classes_remaining'] if student['classes_remaining'] is not None else 0

        # Рассчитываем количество пропущенных занятий
        missed_classes_result = await calculate_missed_classes(student_id, start_date_dt, end_date_dt)

        if not missed_classes_result["success"]:
            return missed_classes_result

        missed_classes = missed_classes_result["missed_classes"]

        if missed_classes == 0:
            return {"success": False, "error": "За указанный период у ученика не было запланированных занятий"}

        # Обновляем баланс ученика
        new_balance = current_balance + missed_classes

        await execute_raw_sql(
            "UPDATE public.student SET classes_remaining = $1 WHERE id = $2;",
            new_balance, student_id
        )

        # Записываем информацию о справке в историю
        await execute_raw_sql(
            """INSERT INTO public.medical_certificates 
                (student_id, start_date, end_date, missed_classes, added_classes, processed_date) 
            VALUES ($1, $2, $3, $4, $5, CURRENT_DATE);""",
            student_id, start_date_dt, end_date_dt, missed_classes, missed_classes
        )

        return {
            "success": True,
            "student_name": student['name'],
            "start_date": start_date,
            "end_date": end_date,
            "missed_classes": missed_classes,
            "classes_added": missed_classes,
            "new_balance": new_balance,
            "message": f"Справка обработана! Возвращено {missed_classes} занятий"
        }

    except ValueError as e:
        return {"success": False, "error": f"Неверный формат даты: {str(e)}"}
    except Exception as e:
        logger.error(f"Error processing medical certificate: {str(e)}")
        return {"success": False, "error": f"Системная ошибка: {str(e)}"}


async def calculate_missed_classes(student_id: int, start_date, end_date) -> dict:
    """Рассчитывает количество пропущенных занятий за период болезни"""
    try:


        # Получаем расписание ученика
        schedule_data = await execute_raw_sql(
            """SELECT DISTINCT sched.day_week, sched.time_start
            FROM public.student_schedule ss
            JOIN public.schedule sched ON ss.schedule = sched.id
            WHERE ss.student = $1;""",
            student_id
        )

        if not schedule_data:
            return {"success": False, "error": "У ученика нет расписания", "missed_classes": 0}

        weekdays_ru_to_int = {
            'понедельник': 0,
            'вторник': 1,
            'среда': 2,
            'четверг': 3,
            'пятница': 4,
            'суббота': 5,
            'воскресенье': 6
        }

        student_weekdays = [weekdays_ru_to_int[row['day_week']] for row in schedule_data]

        missed_classes = 0
        current_date = start_date

        while current_date <= end_date:
            if current_date.weekday() in student_weekdays:
                missed_classes += 1
            current_date += timedelta(days=1)

        return {
            "success": True,
            "missed_classes": missed_classes,
            "schedule_days": len(schedule_data)
        }

    except Exception as e:
        logger.error(f"Error calculating missed classes: {str(e)}")
        return {"success": False, "error": f"Ошибка расчета пропущенных занятий: {str(e)}", "missed_classes": 0}


async def get_student_medical_certificates(student_id: int):
    """Получает список медицинских справок ученика"""
    try:
        certificates = await execute_raw_sql(
            """SELECT 
                id,
                TO_CHAR(start_date, 'DD.MM.YYYY') as start_date,
                TO_CHAR(end_date, 'DD.MM.YYYY') as end_date,
                missed_classes,
                added_classes,
                TO_CHAR(processed_date, 'DD.MM.YYYY') as processed_date
            FROM public.medical_certificates 
            WHERE student_id = $1
            ORDER BY start_date DESC;""",
            student_id
        )

        return certificates
    except Exception as e:
        logger.error(f"Error getting medical certificates: {str(e)}")
        return []


async def delete_medical_certificate(certificate_id: int, student_id: int) -> dict:
    """
    Удаляет справку по болезни и корректирует баланс
    """
    try:
        # Получаем данные о справке
        cert_data = await execute_raw_sql(
            """SELECT missed_classes, added_classes 
            FROM public.medical_certificates 
            WHERE id = $1 AND student_id = $2;""",
            certificate_id, student_id
        )

        if not cert_data:
            return {"success": False, "error": "Справка не найдена"}

        cert = cert_data[0]
        classes_to_remove = cert['added_classes'] or cert['missed_classes'] or 0

        if classes_to_remove <= 0:
            return {"success": False, "error": "Некорректное количество занятий в справке"}

        # Получаем текущий баланс ученика
        student_data = await execute_raw_sql(
            "SELECT classes_remaining FROM public.student WHERE id = $1;",
            student_id
        )

        if not student_data:
            return {"success": False, "error": "Ученик не найден"}

        current_balance = student_data[0]['classes_remaining'] or 0

        # Проверяем, что баланс не уйдет в минус
        new_balance = current_balance - classes_to_remove
        if new_balance < 0:
            return {"success": False, "error": "Нельзя удалить справку: баланс уйдет в отрицательное значение"}

        # Обновляем баланс
        await execute_raw_sql(
            "UPDATE public.student SET classes_remaining = $1 WHERE id = $2;",
            new_balance, student_id
        )

        # Удаляем справку
        await execute_raw_sql(
            "DELETE FROM public.medical_certificates WHERE id = $1;",
            certificate_id
        )

        return {
            "success": True,
            "message": f"Справка удалена. С баланса снято {classes_to_remove} занятий",
            "classes_removed": classes_to_remove,
            "new_balance": new_balance
        }

    except Exception as e:
        logger.error(f"Error deleting medical certificate: {str(e)}")
        return {"success": False, "error": f"Системная ошибка: {str(e)}"}