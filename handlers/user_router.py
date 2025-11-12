from typing import Dict, Optional

import pytz
from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, \
    CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.dialects.postgresql import asyncpg

from config import settings
from create_bot import bot, get_redis_storage
from database.database_module import create_visit_record_model
from database.schemas import schema
from db_handler.db_funk import get_user_data, insert_user, execute_raw_sql
from keyboards.kbs import main_kb, home_page_kb, places_kb
from utils.utils import get_refer_id, get_now_time, get_current_week_day, get_belt_emoji
from aiogram.utils.chat_action import ChatActionSender
import logging
from datetime import datetime, time

logging.basicConfig(level=logging.ERROR)

user_router = Router()

# Инициализация redis_storage
redis_storage = get_redis_storage()

universe_text = ('https://superset.srm-1legion.ru/ - наша админка')





@user_router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    async with ChatActionSender.typing(bot=bot, chat_id=message.from_user.id):
        # Сначала проверяем кэш
        cached_user = None
        if redis_storage:
            cached_user = await redis_storage.get_user_data(message.from_user.id, "profile")

        if cached_user:
            permissions_dict = {0: 'Гость', 1: 'Тренер', 2: 'Администратор', 3: 'Родитель', 4: 'Студент',
                                99: 'Разработчик'}
            permissions = permissions_dict.get(cached_user.get('permissions'))
            response_text = f'Приветствую вас {permissions} {cached_user.get("telegram_username")}, Вижу что вы уже в моей базе данных. {universe_text}'
        else:
            user_info = await get_user_data(user_id=message.from_user.id)
            if user_info:
                permissions_dict = {0: 'Гость', 1: 'Тренер', 2: 'Администратор', 3: 'Родитель', 4: 'Студент',
                                    99: 'Разработчик'}
                permissions = permissions_dict.get(user_info.get('permissions'))
                response_text = f'Приветствую вас {permissions} {user_info.get("telegram_username")}, Вижу что вы уже в моей базе данных. {universe_text}'

                # Сохраняем в кэш
                if redis_storage:
                    await redis_storage.set_user_data(message.from_user.id, "profile", user_info, 3600)
            else:
                user_data = {
                    'telegram_id': message.from_user.id,
                    'permissions': 0,
                    'telegram_username': message.from_user.full_name,
                    'refer_id': None,
                    'date_reg': datetime.now()
                }
                await insert_user(user_data)
                response_text = f'{message.from_user.full_name}, вы зарегистрированы в боте {universe_text}'

        await message.answer(text=response_text, reply_markup=await main_kb(message.from_user.id))


@user_router.message(F.text.contains('Назад'))
async def cmd_start(message: Message):
    await message.answer(f'{message.from_user.first_name}, Вижу что вы уже в моей базе данных. {universe_text}',
                         reply_markup=await main_kb(message.from_user.id))


# хендлер профиля
@user_router.message(Command('profile'))
@user_router.message(F.text.contains('Мой профиль'))
async def get_profile(message: Message):
    async with ChatActionSender.typing(bot=bot, chat_id=message.from_user.id):
        # Проверяем кэш
        cached_user = None
        if redis_storage:
            cached_user = await redis_storage.get_user_data(message.from_user.id, "profile")

        if cached_user:
            user_info = cached_user
        else:
            user_info = await get_user_data(user_id=message.from_user.id)
            if redis_storage and user_info:
                await redis_storage.set_user_data(message.from_user.id, "profile", user_info, 3600)

        if user_info:
            permissions_dict = {0: 'Гость', 1: 'Тренер', 2: 'Администратор', 3: 'Родитель', 4: 'Студент',
                                99: 'Разработчик'}
            permissions = permissions_dict.get(user_info.get('permissions'))

            text = (f'👉 Ваш телеграм ID: <code><b>{message.from_user.id}</b></code> , права {permissions} \n')

        await message.answer(text, reply_markup=await main_kb(message.from_user.id))


# Обработчик кнопки "Посещения" с проверкой прав (оптимизированный)
@user_router.message(F.text.contains('⚙️ Посещения'))
async def handle_visits(message: types.Message):
    try:
        # Проверяем кэш прав
        cached_permissions = None
        if redis_storage:
            cached_permissions = await redis_storage.get_user_data(message.from_user.id, "permissions")

        if cached_permissions is not None:
            user_permission = cached_permissions
        else:
            user_permission = await execute_raw_sql(
                f"""SELECT permissions FROM {schema}.telegram_user 
                WHERE telegram_id = {message.from_user.id};"""
            )
            if user_permission:
                user_permission = user_permission[0]['permissions']
                if redis_storage:
                    await redis_storage.set_user_data(message.from_user.id, "permissions", user_permission, 7200)

        if user_permission and user_permission in (1, 2, 99):
            await message.answer("Выберите место:", reply_markup=places_kb())
        else:
            await message.answer("⛔ Доступ запрещен", reply_markup=types.ReplyKeyboardRemove())

    except Exception as e:
        await message.answer("⚠️ Ошибка проверки прав доступа")
        print(f"Permission check error: {str(e)}")


# Состояния FSM
class TrainingStates(StatesGroup):
    waiting_for_time = State()
    waiting_for_extra_student = State()


async def get_trainer_name(trainer_id: int) -> str:
    """Получает имя тренера по ID"""
    trainer_data = await execute_raw_sql(
        f"SELECT name FROM {schema}.trainer WHERE id = $1;",
        trainer_id
    )
    return trainer_data[0]['name'] if trainer_data else f"Тренер #{trainer_id}"


async def get_place_name(place_id: int) -> str:
    """Получает название места по ID"""
    place_data = await execute_raw_sql(
        f"SELECT name FROM {schema}.training_place WHERE id = $1;",
        place_id
    )
    return place_data[0]['name'] if place_data else f"Место #{place_id}"


async def get_schedule_time(schedule_id: int) -> Optional[time]:
    """Получает время тренировки по ID расписания"""
    schedule_data = await execute_raw_sql(
        f"SELECT time_start FROM {schema}.schedule WHERE id = $1;",
        schedule_id
    )
    return schedule_data[0]['time_start'] if schedule_data else None


# --- Обработчики ---
@user_router.message(F.text.in_(['🥋 ГМР', '🥋 Сормовская', '🥋 Ставрапольская']))
async def handle_city_selection(message: Message, state: FSMContext):
    """Обработчик выбора места тренировки"""
    try:
        selected_place_name = message.text.replace('🥋 ', '')
        today_weekday = get_current_week_day()

        print(f"🔍 Выбрано место: {selected_place_name}, день недели: {today_weekday}")

        # Получаем ID места тренировки
        place_data = await execute_raw_sql(
            f"SELECT id FROM {schema}.training_place WHERE name = $1;",
            selected_place_name
        )

        if not place_data:
            await message.answer("❌ Место тренировки не найдено в базе данных")
            return

        place_id = place_data[0]['id']
        print(f"🔍 ID места {selected_place_name}: {place_id}")

        # Получаем тренировки на сегодня
        trainings = await execute_raw_sql(
            f"""SELECT s.id as schedule_id, s.time_start, s.time_end, 
                  s.sport_discipline, sp.name as discipline_name, s.day_week
            FROM {schema}.schedule s
            JOIN {schema}.sport sp ON s.sport_discipline = sp.id
            WHERE s.training_place = $1 AND s.day_week = $2
            ORDER BY s.time_start;""",
            place_id, today_weekday
        )

        print(f"🔍 Найдено тренировок: {len(trainings)}")

        if not trainings:
            await message.answer(f"❌ На {selected_place_name} сегодня нет тренировок.")
            return

        # ПРЕОБРАЗУЕМ Record ОБЪЕКТЫ В СЛОВАРИ для сериализации
        trainings_serializable = []
        for training in trainings:
            training_dict = {
                'schedule_id': training['schedule_id'],
                'time_start': training['time_start'].isoformat() if training['time_start'] else None,
                'time_end': training['time_end'].isoformat() if training['time_end'] else None,
                'sport_discipline': training['sport_discipline'],
                'discipline_name': training['discipline_name'],
                'day_week': training['day_week']
            }
            trainings_serializable.append(training_dict)

        # Сохраняем данные в состоянии
        await state.update_data(
            place_id=place_id,
            place_name=selected_place_name,
            trainings=trainings_serializable  # Используем сериализуемые данные
        )

        # Кэшируем в Redis (если доступен) - ТЕПЕРЬ С СЕРИАЛИЗУЕМЫМИ ДАННЫМИ
        if redis_storage:
            cache_key = f"trainings:{selected_place_name}:{today_weekday}"
            try:
                await redis_storage.set_user_data(
                    message.from_user.id,
                    cache_key,
                    trainings_serializable,  # Сериализуемые данные
                    1800
                )
            except Exception as e:
                print(f"⚠️ Ошибка кэширования: {e}")

        # Создаем клавиатуру с тренировками
        builder = InlineKeyboardBuilder()
        for training in trainings:  # Используем оригинальные данные для отображения
            start = training['time_start'].strftime("%H:%M") if isinstance(training['time_start'], time) else training[
                'time_start']
            end = training['time_end'].strftime("%H:%M") if isinstance(training['time_end'], time) else training[
                'time_end']
            builder.button(
                text=f"{start}-{end} ({training['discipline_name']})",
                callback_data=f"training:{training['schedule_id']}"
            )

        builder.adjust(1)
        await message.answer(
            f"🏢 Место: {selected_place_name}\n"
            f"📅 День: {today_weekday}\n"
            f"Выберите время тренировки:",
            reply_markup=builder.as_markup()
        )
        await state.set_state(TrainingStates.waiting_for_time)

    except Exception as e:
        await message.answer("❌ Ошибка при загрузке данных. Попробуйте позже.")
        print(f"Error in handle_city_selection: {str(e)}")


@user_router.callback_query(TrainingStates.waiting_for_time, F.data.startswith("training:"))
async def handle_time_selection(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора времени тренировки"""
    try:
        _, schedule_id = callback.data.split(":")
        data = await state.get_data()

        # Находим выбранную тренировку
        selected_training = next(
            (t for t in data['trainings'] if str(t['schedule_id']) == schedule_id),
            None
        )
        if not selected_training:
            await callback.answer("Тренировка не найдена", show_alert=True)
            return

        # Получаем данные тренера
        trainer_data = await execute_raw_sql(
            f"SELECT id, name FROM {schema}.trainer WHERE telegram_id = $1;",
            callback.from_user.id
        )
        if not trainer_data:
            await callback.answer("⛔ Вы не зарегистрированы как тренер", show_alert=True)
            return

        trainer_id = trainer_data[0]['id']
        trainer_name = trainer_data[0]['name']

        # Проверяем кэш студентов
        cache_key = f"students:schedule:{schedule_id}"
        cached_students = None
        if redis_storage:
            cached_students = await redis_storage.get_user_data(callback.from_user.id, cache_key)

        if cached_students:
            students = cached_students
        else:
            # Получаем студентов на тренировку
            students_raw = await execute_raw_sql(
                f"""SELECT st.id, st.name 
                FROM {schema}.student_schedule ss
                JOIN {schema}.student st ON ss.student = st.id
                WHERE ss.schedule = $1 AND st.active = true;""",
                int(schedule_id)
            )

            # Преобразуем в сериализуемый формат
            students = [{'id': s['id'], 'name': s['name']} for s in students_raw]

            # Сохраняем в кэш на 1 час
            if redis_storage and students:
                await redis_storage.set_user_data(callback.from_user.id, cache_key, students, 3600)

        if not students:
            await callback.message.answer("На этой тренировке нет записанных студентов.")
            await state.clear()
            return

        # Получаем текущий выбор студентов из Redis
        selected_students = {}
        if redis_storage:
            selected_students = await redis_storage.get_selected_students(callback.from_user.id)

        # Создаем клавиатуру со студентами
        builder = InlineKeyboardBuilder()
        for student in students:
            student_id = str(student['id'])
            is_selected = student_id in selected_students
            builder.button(
                text=f"{'☑️' if is_selected else '⬜️'} {student['name']}",
                callback_data=f"student:{student_id}"
            )

        # Добавляем кнопку подтверждения
        builder.button(
            text="✅ Подтвердить посещение",
            callback_data=f"confirm:{schedule_id}:{trainer_id}:{data['place_id']}:{selected_training['sport_discipline']}"
        )

        # Добавляем кнопку "+ ученик"
        builder.button(
            text="➕ ученик",
            callback_data=f"extra_student:{schedule_id}:{trainer_id}:{data['place_id']}:{selected_training['sport_discipline']}"
        )

        # Добавляем кнопку для просмотра статуса посещения
        builder.button(
            text="📊 Показать кто пришел",
            callback_data=f"show_attendance:{schedule_id}"
        )

        builder.adjust(1)

        # Форматируем время (обрабатываем как строку, так и datetime)
        if 'time_start' in selected_training and selected_training['time_start']:
            if isinstance(selected_training['time_start'], str):
                # Если это строка из кэша
                start_time = selected_training['time_start'][11:16]  # Извлекаем время из ISO строки
            else:
                # Если это datetime объект
                start_time = selected_training['time_start'].strftime("%H:%M")
        else:
            start_time = "??:??"

        await callback.message.edit_text(
            f"👨‍🏫 Тренер: {trainer_name}\n"
            f"🏢 Место: {data['place_name']}\n"
            f"🕒 Время: {start_time}\n"
            f"🧘 Дисциплина: {selected_training['discipline_name']}\n"
            "Выберите студентов:",
            reply_markup=builder.as_markup()
        )

        await callback.answer()
        await state.clear()

    except Exception as e:
        await callback.answer("Ошибка при загрузке данных", show_alert=True)
        print(f"Error in handle_time_selection: {str(e)}")
        await state.clear()

@user_router.callback_query(F.data.startswith("student:"))
async def select_student(callback: CallbackQuery):
    """Обработчик выбора студента"""
    try:
        if not redis_storage:
            await callback.answer("Система временно недоступна", show_alert=True)
            return

        _, student_id = callback.data.split(":")
        user_id = callback.from_user.id

        # Получаем текущий выбор из Redis
        selected_students = await redis_storage.get_selected_students(user_id)

        # Обновляем клавиатуру
        new_keyboard = []
        for row in callback.message.reply_markup.inline_keyboard:
            new_row = []
            for button in row:
                if button.callback_data == callback.data:
                    student_name = button.text[2:]  # Убираем эмодзи

                    if student_id in selected_students:
                        # Удаляем студента из выбора
                        await redis_storage.remove_student(user_id, student_id)
                        new_text = f"⬜️ {student_name}"
                    else:
                        # Добавляем студента в выбор
                        await redis_storage.add_student(user_id, student_id, student_name)
                        new_text = f"☑️ {student_name}"

                    new_row.append(InlineKeyboardButton(text=new_text, callback_data=button.callback_data))
                else:
                    new_row.append(button)
            new_keyboard.append(new_row)

        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(inline_keyboard=new_keyboard)
        )
        await callback.answer()

    except Exception as e:
        await callback.answer("Ошибка при выборе", show_alert=True)
        print(f"Error in select_student: {str(e)}")


@user_router.callback_query(F.data.startswith("confirm:"))
async def confirm_attendance(callback: CallbackQuery):
    try:
        user_id = callback.from_user.id

        # Получаем выбранных студентов из Redis
        selected_students = {}
        if redis_storage:
            selected_students = await redis_storage.get_selected_students(user_id)

        if not selected_students:
            await callback.answer("Выберите хотя бы одного студента!", show_alert=True)
            return

        # Парсим параметры
        _, schedule_id, trainer_id, place_id, discipline_id = callback.data.split(":")
        schedule_id = int(schedule_id)
        trainer_id = int(trainer_id)
        place_id = int(place_id)
        discipline_id = int(discipline_id)

        # Получаем данные тренировки
        schedule_data = await execute_raw_sql(
            f"SELECT time_start FROM {schema}.schedule WHERE id = $1;",
            schedule_id
        )
        if not schedule_data:
            await callback.answer("Расписание не найдено", show_alert=True)
            return

        # Работа с временем - используем наивные datetime (без временной зоны)
        current_datetime = datetime.now()
        current_date = current_datetime.date()
        schedule_time = schedule_data[0]['time_start']

        # Сохраняем посещения
        success_count = 0
        skipped_count = 0
        errors = []

        for student_id_str, student_name in selected_students.items():
            try:
                student_id = int(student_id_str)

                # Проверка на дубликат (используем только дату)
                existing = await execute_raw_sql(
                    f"""SELECT 1 FROM {schema}.visit 
                    WHERE student = $1 AND shedule = $2 
                    AND DATE(data) = $3 LIMIT 1;""",
                    student_id, schedule_id, current_date
                )

                if existing:
                    skipped_count += 1
                    continue

                # Сохраняем наивный datetime (без временной зоны)
                await execute_raw_sql(
                    f"""INSERT INTO {schema}.visit (
                        data, trainer, student, place, sport_discipline, shedule
                    ) VALUES ($1, $2, $3, $4, $5, $6);""",
                    current_datetime,  # Наивный datetime
                    trainer_id,
                    student_id,
                    place_id,
                    discipline_id,
                    schedule_id
                )
                success_count += 1

            except Exception as e:
                errors.append(f"{student_name}: {str(e)}")

        # Формируем отчет
        report = [
            f"📅 Дата: {current_date.strftime('%d.%m.%Y')}",
            f"⏱ Время: {schedule_time.strftime('%H:%M')}",
            f"✅ Успешно: {success_count}",
            f"⏭ Пропущено (дубли): {skipped_count}",
            f"❌ Ошибки: {len(errors)}",
            *[f"• {name}" for name in selected_students.values()]
        ]

        if errors:
            report.append("\nПоследние ошибки:")
            report.extend(errors[:3])

        await callback.message.answer("\n".join(report))

        # ОЧИЩАЕМ ВЫБОР ПОСЛЕ ПОДТВЕРЖДЕНИЯ
        if redis_storage:
            await redis_storage.clear_selected_students(user_id)

        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer()

    except Exception as e:
        await callback.answer("⚠️ Ошибка системы", show_alert=True)
        print(f"Error in confirm_attendance: {str(e)}")


@user_router.callback_query(F.data.startswith("show_attendance:"))
async def show_attendance_status(callback: CallbackQuery):
    """Показывает статус посещения с цветовым кодированием по поясам"""
    try:
        _, schedule_id = callback.data.split(":")
        schedule_id = int(schedule_id)

        current_date = datetime.now().date()

        # Проверяем кэш информации о тренировке
        cache_key = f"training_info:{schedule_id}"
        cached_training_info = None
        if redis_storage:
            cached_training_info = await redis_storage.get_user_data(callback.from_user.id, cache_key)

        if cached_training_info:
            training_info = cached_training_info
        else:
            # Получаем информацию о тренировке
            training_info = await execute_raw_sql(
                f"""SELECT s.time_start, s.time_end, tp.name as place_name, 
                    sp.name as discipline_name
                FROM {schema}.schedule s
                JOIN {schema}.training_place tp ON s.training_place = tp.id
                JOIN {schema}.sport sp ON s.sport_discipline = sp.id
                WHERE s.id = $1;""",
                schedule_id
            )

            if redis_storage and training_info:
                await redis_storage.set_user_data(callback.from_user.id, cache_key, training_info, 1800)

        if not training_info:
            await callback.answer("Информация о тренировке не найдена", show_alert=True)
            return

        training = training_info[0]

        # Получаем ВСЕХ студентов, которые пришли на тренировку сегодня
        # Включая тех, кто был добавлен через "+ ученик"
        students = await execute_raw_sql(
            f"""SELECT st.id, st.name, st.birthday, st.rang,
                CASE 
                    WHEN v.id IS NOT NULL THEN 'present'
                    ELSE 'absent'
                END as status
            FROM {schema}.student st
            LEFT JOIN {schema}.student_schedule ss ON ss.student = st.id AND ss.schedule = $1
            LEFT JOIN {schema}.visit v ON v.student = st.id 
                AND v.shedule = $1 
                AND DATE(v.data) = $2
            WHERE st.active = true
            AND (
                ss.schedule = $1  -- Студенты из расписания
                OR EXISTS (        -- ИЛИ студенты, которые пришли через "+ ученик"
                    SELECT 1 FROM {schema}.visit v2 
                    WHERE v2.student = st.id 
                    AND v2.shedule = $1 
                    AND DATE(v2.data) = $2
                )
            )
            ORDER BY 
                CASE 
                    WHEN st.rang IS NULL THEN 999
                    WHEN st.rang ILIKE '%бел%' THEN 1
                    WHEN st.rang ILIKE '%желт%' THEN 2
                    WHEN st.rang ILIKE '%жёлт%' THEN 2 
                    WHEN st.rang ILIKE '%оранж%' THEN 3
                    WHEN st.rang ILIKE '%зелен%' THEN 4
                    WHEN st.rang ILIKE '%син%' THEN 5
                    WHEN st.rang ILIKE '%коричн%' THEN 6
                    WHEN st.rang ILIKE '%красн%' THEN 7
                    WHEN st.rang ILIKE '%черн%' THEN 8
                    ELSE 999
                END, st.name;""",
            schedule_id, current_date
        )

        if not students:
            await callback.answer("На этой тренировке нет записанных студентов", show_alert=True)
            return

        # Форматируем время
        start_time = training['time_start'].strftime("%H:%M") if isinstance(training['time_start'], time) else training[
            'time_start']
        end_time = training['time_end'].strftime("%H:%M") if isinstance(training['time_end'], time) else training[
            'time_end']

        # Создаем сообщение в формате как в примере
        message_lines = [
            f"{training['place_name']}",
            f"Группа {start_time}-{end_time} ({training['discipline_name']})",
            ""
        ]

        present_students = []
        absent_students = []

        for student in students:
            birth_year = student['birthday'].year if student['birthday'] else " "
            belt_emoji = get_belt_emoji(student['rang'])

            student_line = f"{belt_emoji} {student['name']} {birth_year}"

            if student['status'] == 'present':
                present_students.append(student_line)
            else:
                absent_students.append(student_line)

        # Добавляем присутствующих
        for student_line in present_students:
            message_lines.append(student_line)

        # Добавляем отсутствующих
        if absent_students:
            message_lines.extend([
                "",
                "Отсутствуют:"
            ])
            for student_line in absent_students:
                message_lines.append(student_line)

        # Статистика
        message_lines.extend([
            "",
            f"Всего: {len(present_students) + len(absent_students)} чел.",
            f"Присутствуют: {len(present_students)} чел.",
            f"Отсутствуют: {len(absent_students)} чел."
        ])

        await callback.message.answer("\n".join(message_lines))
        await callback.answer()

    except Exception as e:
        await callback.answer("Ошибка при получении статуса посещения", show_alert=True)
        print(f"Error in show_attendance_status: {str(e)}")


async def record_extra_student_visit(student_name: str, trainer_telegram_id: int,
                                     schedule_id: int = None, place_id: int = None,
                                     discipline_id: int = None) -> dict:
    """
    Записывает ученика на тренировку не по расписанию
    """
    try:
        # Ищем ученика
        student_data = await execute_raw_sql(
            f"""SELECT id, name, classes_remaining 
            FROM public.student 
            WHERE active = true 
            AND name ILIKE $1
            LIMIT 1;""",
            f"%{student_name}%"
        )

        if not student_data:
            return {"success": False, "error": f"Ученик '{student_name}' не найден"}

        student = student_data[0]
        student_id = student['id']
        current_balance = student['classes_remaining'] if student['classes_remaining'] is not None else 0

        # Ищем тренера по telegram_id
        trainer_data = await execute_raw_sql(
            f"""SELECT id, name 
            FROM public.trainer 
            WHERE telegram_id = $1
            AND active = true
            LIMIT 1;""",
            trainer_telegram_id
        )

        if not trainer_data:
            return {"success": False, "error": "Тренер не найден"}

        trainer = trainer_data[0]
        trainer_id = trainer['id']

        # Получаем текущие дату и время в правильном формате (без часового пояса)
        current_datetime_data = await execute_raw_sql(f"SELECT NOW()::timestamp as current_datetime;")
        current_datetime = current_datetime_data[0]['current_datetime']
        current_date = current_datetime.date()
        current_time = current_datetime.time()

        # ПРОВЕРКА НА ДУБЛИКАТ: проверяем, не был ли уже ученик записан на эту тренировку сегодня
        existing_visit = await execute_raw_sql(
            f"""SELECT id 
            FROM public.visit 
            WHERE student = $1 
            AND shedule = $2 
            AND DATE(data) = $3
            LIMIT 1;""",
            student_id, schedule_id, current_date
        )

        if existing_visit:
            return {
                "success": False,
                "error": f"Ученик {student['name']} уже записан на эту тренировку сегодня"
            }

        # Проверяем, было ли сегодня уже списание у этого ученика (для любых тренировок)
        today_visits = await execute_raw_sql(
            f"""SELECT COUNT(*) as visit_count 
            FROM public.visit 
            WHERE student = $1 
            AND DATE(data) = $2;""",
            student_id, current_date
        )

        visit_count = today_visits[0]['visit_count'] if today_visits else 0
        class_deducted = False
        new_balance = current_balance

        # Списание занятия только если сегодня еще не было посещений
        if visit_count == 0 and current_balance > 0:
            new_balance = current_balance - 1
            class_deducted = True

            # Обновляем баланс ученика
            await execute_raw_sql(
                f"UPDATE public.student SET classes_remaining = $1 WHERE id = $2;",
                new_balance, student_id
            )

        # Определяем место тренировки
        if not place_id:
            # Если место не передано, используем первое доступное
            place_data = await execute_raw_sql(
                f"SELECT id, name FROM public.training_place LIMIT 1;"
            )
            if not place_data:
                return {"success": False, "error": "Не найдены места тренировок"}
            place = place_data[0]
            place_id = place['id']
        else:
            # Получаем информацию о переданном месте
            place_data = await execute_raw_sql(
                f"SELECT id, name FROM public.training_place WHERE id = $1;",
                place_id
            )
            if not place_data:
                return {"success": False, "error": "Указанное место тренировки не найдено"}
            place = place_data[0]

        # Определяем спортивную дисциплина
        if not discipline_id:
            # Если дисциплина не передана, используем первую доступную
            sport_data = await execute_raw_sql(
                f"SELECT id, name FROM public.sport LIMIT 1;"
            )
            sport_id = sport_data[0]['id'] if sport_data else 1
            sport_name = sport_data[0]['name'] if sport_data else "Неизвестная дисциплина"
        else:
            # Получаем информацию о переданной дисциплине
            sport_data = await execute_raw_sql(
                f"SELECT id, name FROM public.sport WHERE id = $1;",
                discipline_id
            )
            if sport_data:
                sport_id = sport_data[0]['id']
                sport_name = sport_data[0]['name']
            else:
                sport_id = discipline_id
                sport_name = "Неизвестная дисциплина"

        # Создаем запись о посещении (используем timestamp без часового пояса)
        visit_result = await execute_raw_sql(
            f"""INSERT INTO public.visit 
                (data, trainer, student, place, sport_discipline, shedule) 
            VALUES ($1, $2, $3, $4, $5, $6) 
            RETURNING id;""",
            current_datetime, trainer_id, student_id, place_id, sport_id, schedule_id
        )

        if not visit_result:
            return {"success": False, "error": "Ошибка при записи посещения"}

        return {
            "success": True,
            "student_name": student['name'],
            "place_name": place['name'],
            "visit_date": current_date.strftime('%d.%m.%Y'),
            "visit_time": current_time.strftime('%H:%M'),
            "class_deducted": class_deducted,
            "new_balance": new_balance,
            "trainer_name": trainer['name'],
            "sport_name": sport_name,
            "schedule_id": schedule_id
        }

    except Exception as e:
        print(f"Error recording extra student visit: {str(e)}")
        return {"success": False, "error": f"Системная ошибка: {str(e)}"}


@user_router.callback_query(F.data.startswith("extra_student:"))
async def handle_extra_student(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки '+ ученик' для записи ученика не по расписанию"""
    try:
        _, schedule_id, trainer_id, place_id, discipline_id = callback.data.split(":")

        # Сохраняем данные в состоянии для использования в следующем шаге
        await state.update_data(
            schedule_id=int(schedule_id),
            trainer_id=int(trainer_id),
            place_id=int(place_id),
            discipline_id=int(discipline_id)
        )

        await callback.message.answer(
            "➕ Запись ученика не по расписанию\n\n"
            "Введите ФИО ученика:\n\n"
            "Например:\n"
            "<code>Аносова Кира</code>\n\n"
            "Или:\n"
            "<code>Иванов Петр</code>"
        )

        # Устанавливаем состояние ожидания имени ученика
        await state.set_state(TrainingStates.waiting_for_extra_student)
        await callback.answer()

    except Exception as e:
        await callback.answer("Ошибка при обработке запроса", show_alert=True)
        print(f"Error in handle_extra_student: {str(e)}")


@user_router.message(TrainingStates.waiting_for_extra_student)
async def process_extra_student_name(message: Message, state: FSMContext):
    """Обработка введенного имени ученика не по расписанию"""
    try:
        student_name = message.text.strip()
        data = await state.get_data()

        # Используем нашу функцию для записи ученика
        result = await record_extra_student_visit(
            student_name=student_name,
            trainer_telegram_id=message.from_user.id,
            schedule_id=data.get('schedule_id'),
            place_id=data.get('place_id'),
            discipline_id=data.get('discipline_id')
        )

        if result["success"]:
            response_text = (
                f"✅ Ученик записан на тренировку!\n\n"
                f"👤 Ученик: <b>{result['student_name']}</b>\n"
                f"🏢 Место: <b>{result['place_name']}</b>\n"
                f"📅 Дата: <b>{result['visit_date']}</b>\n"
                f"⏰ Время: <b>{result['visit_time']}</b>\n"
            )

            if result['class_deducted']:
                response_text += f"📊 Списано занятие: <b>Да</b>\n"
                response_text += f"🎯 Новый баланс: <b>{result['new_balance']}</b> занятий"
            else:
                response_text += f"📊 Списано занятие: <b>Нет</b> (уже списано сегодня)\n"
                response_text += f"🎯 Текущий баланс: <b>{result['new_balance']}</b> занятий"
        else:
            response_text = f"❌ Ошибка: {result['error']}"

        await message.answer(response_text)
        await state.clear()

    except Exception as e:
        await message.answer(f"❌ Произошла ошибка: {str(e)}")
        await state.clear()