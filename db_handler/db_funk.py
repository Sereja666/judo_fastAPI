

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


async def get_all_users(table_name='student', schema_name='schema', count=False):
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


# asyncio.run(create_table_users())


# async def get_current_scheduler(user_id: int, name: str, ):
#
#     # Преобразуем текущее время в формат HH:MM
#     cur_time = datetime.datetime.now().strftime("%H:%M")
#     print(cur_time)
#     week_day = get_current_week_day()
#
#     async with db_manager as client:
#         # Получаем ID места тренировки по имени
#         training_place_id_query = select(Training_place).where(Training_place.name == name)
#
#         training_place = await client.execute(training_place_id_query)
#         training_place_id = training_place.scalar_one_or_none()
#
#         if training_place_id is None:
#             return None  # Если место не найдено, возвращаем None или обрабатываем ошибку
#
#         # Выполняем запрос к таблице Schedule
#         user_data = await client.select_data(
#             table_name='schedule',
#             where_dict={
#                 'day_week': week_day,
#                 'time_start <= ': cur_time,  # Условие для начала времени
#                 'time_end >= ': cur_time,  # Условие для окончания времени
#                 'training_place': training_place_id.id  # Условие для ID места тренировки
#             },
#             one_dict=True
#         )
#     print(user_data)
#     return user_data


# async def get_current_scheduler(user_id: int, name: str):
#     cur_time = datetime.now().strftime("%H:%M")
#     week_day = get_current_week_day()
#     name = name.replace('_', '')
#
#     async with db_manager as client:
#         # Получаем ID места тренировки по имени
#         training_place_data = await client.select_data(
#             table_name='training_place',
#             where_dict={'name': name},
#             one_dict=True
#         )
#
#         if training_place_data is None or len(training_place_data) == 0:
#             return None  # Если место не найдено, возвращаем None
#
#         print("training_place_data", training_place_data)
#         print("cur_time", cur_time)
#         training_place_id = training_place_data['id']
#
#         # Здесь вы можете добавить логику для получения расписания на основе training_place_id
#         # Используем where_dict для простых условий
#         where_dict = {
#             'day_week': week_day,
#             'training_place': training_place_id
#         }
#
#         # Получаем расписание, добавляя условия для времени
#         schedule_data = await client.select_data(
#             table_name='schedule',
#             where_dict=where_dict,
#             additional_conditions=[
#                 ('time_start', '<=', cur_time),
#                 ('time_end', '>=', cur_time)
#             ],
#             one_dict=True
#         )
#
#         return schedule_data  # Возвращаем данные расписания




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