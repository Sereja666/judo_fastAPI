

from config import settings

from create_bot import db_manager

import asyncpg




# функция, для получения информации по конкретному пользователю
async def get_user_data(user_id: int, table_name='telegram_user'):
    async with db_manager as client:
        user_data = await client.select_data(table_name=table_name, where_dict={'telegram_id': user_id}, one_dict=True)
    return user_data



# функция, для получения всех пользователей (для админки)
async def get_all_users(table_name='student', count=False):
    async with db_manager as client:
        all_users = await client.select_data(table_name=table_name)
    if count:
        return len(all_users)
    else:
        return all_users


#

# функция, для добавления пользователя в базу данных
async def insert_user(user_data: dict, table_name='users_reg'):
    async with db_manager as client:
        await client.insert_data_with_update(table_name=table_name, records_data=user_data, conflict_column='user_id')
        if user_data.get('refer_id'):
            refer_info = await client.select_data(table_name=table_name,
                                                  where_dict={'user_id': user_data.get('refer_id')},
                                                  one_dict=True, columns=['user_id', 'count_refer'])
            await client.update_data(table_name=table_name,
                                     where_dict={'user_id': refer_info.get('user_id')},
                                     update_dict={'count_refer': refer_info.get('count_refer') + 1})

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




async def execute_raw_sql(query: str):
    # Установите соединение с базой данных
    print('Начинаю соединение')
    conn = await asyncpg.connect(
        user=settings.db.user,
        password=settings.db.password,
        database=settings.db.db,  # Убедитесь, что это строка
        host=settings.db.host,
        port=settings.db.port
    )
    try:
        # Выполнение SQL запроса
        result = await conn.fetch(query)
        return result  # Возвращаем результат запроса
    finally:
        # Закрываем соединение
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
                        f"UPDATE public.visit SET "
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
                        f"INSERT INTO public.visit "
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