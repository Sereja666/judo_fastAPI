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
from create_bot import bot
from database.database_module import create_visit_record_model
from database.schemas import schema
from database import redis_storage
from db_handler.db_funk import get_user_data, insert_user, execute_raw_sql
from keyboards.kbs import main_kb, home_page_kb, places_kb
from utils.utils import get_refer_id, get_now_time, get_current_week_day, get_belt_emoji
from aiogram.utils.chat_action import ChatActionSender
import logging
from datetime import datetime, time


logging.basicConfig(level=logging.ERROR)

user_router = Router()

universe_text = ('Чтоб получить информацию о своем профиле воспользуйся кнопкой "Мой профиль" или специальной '
                 'командой из командного меню.')


@user_router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    async with ChatActionSender.typing(bot=bot, chat_id=message.from_user.id):
        user_info = await get_user_data(user_id=message.from_user.id)

        if user_info:
            permissions_dict = {0: 'Гость', 1: 'Тренер', 2: 'Администратор', 3: 'Родитель', 4: 'Студент',
                                99: 'Разработчик'}
            permissions = permissions_dict.get(user_info.get('permissions'))

            response_text = f'Приветствую вас {permissions}  {user_info.get("telegram_username")}, Вижу что вы уже в моей базе данных. {universe_text}'
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

        await message.answer(text=response_text, reply_markup=main_kb(message.from_user.id))

@user_router.message(F.text.contains('Назад'))
async def cmd_start(message: Message):
    await message.answer(f'{message.from_user.first_name}, Вижу что вы уже в моей базе данных. {universe_text}',
                         reply_markup=main_kb(message.from_user.id))


# хендлер профиля
@user_router.message(Command('profile'))
@user_router.message(F.text.contains('Мой профиль'))
async def get_profile(message: Message):
    async with ChatActionSender.typing(bot=bot, chat_id=message.from_user.id):
        user_info = await get_user_data(user_id=message.from_user.id)

        if user_info:
            permissions_dict = {0: 'Гость', 1: 'Тренер', 2: 'Администратор', 3: 'Родитель', 4: 'Студент',
                                99: 'Разработчик'}
            permissions = permissions_dict.get(user_info.get('permissions'))

            text = (f'👉 Ваш телеграм ID: <code><b>{message.from_user.id}</b></code> , права {permissions} \n')

    await message.answer(text, reply_markup=home_page_kb(message.from_user.id))


# Словарь для хранения выбранных студентов {id: name}
selected_students = {}


# Обработчик кнопки "Посещения" с проверкой прав (оптимизированный)
@user_router.message(F.text.contains('⚙️ Посещения'))
async def handle_visits(message: types.Message):
    try:
        # Проверяем права пользователя
        print(f" # Проверяем права пользователя {message.from_user.id}")
        user_permission = await execute_raw_sql(
            f"""SELECT permissions FROM {schema}.telegram_user 
            WHERE telegram_id = {message.from_user.id};"""
        )
        print(user_permission)
        if user_permission and user_permission[0]['permissions'] in (1, 2, 99):
            await message.answer("Выберите место:", reply_markup=places_kb())
        else:
            await message.answer("⛔ Доступ запрещен", reply_markup=types.ReplyKeyboardRemove())

    except Exception as e:
        await message.answer("⚠️ Ошибка проверки прав доступа")
        print(f"Permission check error: {str(e)}")


# Состояния FSM
class TrainingStates(StatesGroup):
    waiting_for_time = State()






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

        # Получаем ID места тренировки
        place_data = await execute_raw_sql(
            f"SELECT id FROM {schema}.training_place WHERE name = $1;",
            selected_place_name
        )

        if not place_data:
            await message.answer("Место тренировки не найдено")
            return

        place_id = place_data[0]['id']
        today_weekday = get_current_week_day()
        print(today_weekday)
        # Получаем тренировки на сегодня
        trainings = await execute_raw_sql(
            f"""SELECT s.id as schedule_id, s.time_start, s.time_end, 
                  s.sport_discipline, sp.name as discipline_name
            FROM {schema}.schedule s
            JOIN {schema}.sport sp ON s.sport_discipline = sp.id
            WHERE s.training_place = $1 AND s.day_week = $2
            ORDER BY s.time_start;""",
            place_id, today_weekday
        )

        if not trainings:
            await message.answer(f"На {selected_place_name} сегодня нет тренировок.")
            return

        # Сохраняем данные в состоянии
        await state.update_data(
            place_id=place_id,
            place_name=selected_place_name,
            trainings=trainings
        )

        # Создаем клавиатуру с тренировками
        builder = InlineKeyboardBuilder()
        for training in trainings:
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
            f"🏢 Место: {selected_place_name}\nВыберите время тренировки:",
            reply_markup=builder.as_markup()
        )
        await state.set_state(TrainingStates.waiting_for_time)

    except Exception as e:
        await message.answer("Ошибка при загрузке данных. Попробуйте позже.")
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

        # Получаем студентов на тренировку
        students = await execute_raw_sql(
            f"""SELECT st.id, st.name 
            FROM {schema}.student_schedule ss
            JOIN {schema}.student st ON ss.student = st.id
            WHERE ss.schedule = $1 AND st.active = true;""",
            int(schedule_id)
        )

        if not students:
            await callback.message.answer("На этой тренировке нет записанных студентов.")
            await state.clear()
            return

        # Создаем клавиатуру со студентами
        builder = InlineKeyboardBuilder()
        for student in students:
            student_id = str(student['id'])
            builder.button(
                text=f"{'☑️' if student_id in selected_students else '⬜️'} {student['name']}",
                callback_data=f"student:{student_id}"
            )

        # Добавляем кнопку подтверждения
        builder.button(
            text="✅ Подтвердить посещение",
            callback_data=f"confirm:{schedule_id}:{trainer_id}:{data['place_id']}:{selected_training['sport_discipline']}"
        )

        # ДОБАВЛЯЕМ КНОПКУ ДЛЯ ПРОСМОТРА СТАТУСА ПОСЕЩЕНИЯ
        builder.button(
            text="📊 Показать кто пришел",
            callback_data=f"show_attendance:{schedule_id}"
        )

        builder.adjust(1)

        # Форматируем время
        start_time = selected_training['time_start'].strftime("%H:%M") if isinstance(selected_training['time_start'],
                                                                                     time) else selected_training[
            'time_start']

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

        if not training_info:
            await callback.answer("Информация о тренировке не найдена", show_alert=True)
            return

        training = training_info[0]

        # Получаем студентов с информацией о поясе
        students = await execute_raw_sql(
            f"""SELECT st.id, st.name, st.birthday, st.rang,
                CASE 
                    WHEN v.id IS NOT NULL THEN 'present'
                    ELSE 'absent'
                END as status
            FROM {schema}.student_schedule ss
            JOIN {schema}.student st ON ss.student = st.id
            LEFT JOIN {schema}.visit v ON v.student = st.id 
                AND v.shedule = $1 
                AND DATE(v.data) = $2
            WHERE ss.schedule = $1 AND st.active = true
            ORDER BY 
                CASE 
                    WHEN st.rang IS NULL THEN 999
                    WHEN st.rang ILIKE '%бел%' THEN 1
                    WHEN st.rang ILIKE '%желт%' THEN 2
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
            birth_year = student['birthday'].year if student['birthday'] else "неизв."
            belt_emoji = get_belt_emoji(student['rang'])

            student_line = f"{belt_emoji}{student['name']} {birth_year}"

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