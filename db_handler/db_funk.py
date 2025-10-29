

from config import settings

from create_bot import db_manager, logger

import asyncpg

from database.schemas import schema


# функция, для получения информации по конкретному пользователю
async def get_user_data(user_id: int, table_name=f'{schema}.telegram_user'):
    conn = await asyncpg.connect(**settings.db.pg_link)
    try:
        print(f'пытаюсь получить инфу о {user_id}')
        row = await conn.fetchrow(
            f"SELECT * FROM {table_name} WHERE telegram_id = $1",
            user_id
        )
        print(row)
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


#

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
            f"SELECT permissions FROM public.telegram_user WHERE telegram_id = $1;",
            user_telegram_id
        )
        if result:
            return result[0]['permissions']
        else:
            return 0  # Гость по умолчанию
    except Exception as e:
        print(f"Error getting user permissions: {str(e)}")
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
        print(f"Database error: {str(e)}")
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
            f"SELECT date, time_start FROM public.schedule WHERE id = {schedule_id};"
        )

        if not schedule_data:
            return False, "Расписание не найдено"

        # Формируем дату и время посещения
        visit_datetime = f"{schedule_data[0]['date']} {schedule_data[0]['time_start']}"

        # Проверяем существование студентов
        existing_students = await execute_raw_sql(
            f"SELECT id FROM public.student WHERE id IN ({','.join(map(str, student_ids))});"
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
                    f"SELECT id FROM public.visit "
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
                print(f"Ошибка при сохранении для студента {student_id}: {e}")

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
        print(f"Ошибка в save_selection: {e}")
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

        # 2. Обновляем баланс занятий и price_id у ученика
        new_balance = current_balance + classes_to_add
        update_result = await execute_raw_sql(
            f"UPDATE public.student SET classes_remaining = $1, price = $2 WHERE id = $3;",
            new_balance, price_id, student_id  # Теперь записываем price_id вместо amount
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

        return {
            "success": True,
            "student_name": student['name'],
            "amount": amount,
            "price_description": price['description'],
            "classes_added": classes_to_add,
            "new_balance": new_balance,
            "payment_date": payment_date,
            "old_price": old_price_info['price'] if old_price_info else None,
            "new_price": price['price'],
            "price_change_info": price_change_info
        }

    except Exception as e:
        print(f"Error processing payment: {str(e)}")
        return {"success": False, "error": f"Системная ошибка: {str(e)}"}