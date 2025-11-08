import pytz
from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from create_bot import bot
from database.schemas import schema

from db_handler.db_funk import get_user_data, insert_user, execute_raw_sql
from keyboards.kbs import main_kb, home_page_kb, places_kb
from utils.utils import get_refer_id, get_now_time, get_current_week_day
from aiogram.utils.chat_action import ChatActionSender
import logging
from datetime import datetime, time

logging.basicConfig(level=logging.ERROR)

create_user_router = Router()

universe_text = ('Чтоб получить информацию о своем профиле воспользуйся кнопкой "Мой профиль" или специальной '
                 'командой из командного меню.')



@create_user_router.message(F.text == "🥋 Новый ученик")
async def add_new_student(message: Message):
    # Проверяем права
    user_permission = await execute_raw_sql(
        f"SELECT permissions FROM {schema}.telegram_user WHERE telegram_id = {message.from_user.id};"
    )

    if not user_permission or user_permission[0]['permissions'] not in (1, 2, 99):
        await message.answer("⛔ У вас нет прав для добавления учеников")
        return

    await message.answer(
        "Введите данные ученика в формате:\n"
        "ФИО; ДД.ММ.ГГГГ; ID дисциплины; телефон\n\n"
        "Пример:\n"
        "Иванов Петр Сидорович; 15.05.2010; 3; +79161234567",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Отмена")]],
            resize_keyboard=True
        )
    )


class StudentStates(StatesGroup):
    waiting_for_schedule_source = State()


@create_user_router.message(F.text.regexp(r'^[^;]+;[^;]+;[^;]+;[^;]+$'))
async def process_student_data(message: Message, state: FSMContext):
    try:
        # Парсим введенные данные
        parts = [part.strip() for part in message.text.split(';')]
        if len(parts) != 4:
            raise ValueError("Неверное количество параметров")

        name, birthday, discipline_id, phone = parts

        # Валидация данных
        birthday_date = datetime.strptime(birthday, "%d.%m.%Y").date()
        if not discipline_id.isdigit():
            raise ValueError("ID дисциплины должен быть числом")

        # Сохраняем в базу
        result = await execute_raw_sql(
            f"""INSERT INTO {schema}.student (
                name, birthday, sport_discipline, telephone, date_start, price
            ) VALUES (
                '{name}',
                '{birthday_date}',
                {int(discipline_id)},
                '{phone}',
                CURRENT_DATE,
                0
            ) RETURNING id;"""
        )

        new_student_id = result[0]['id']

        # Сохраняем ID нового ученика в состоянии
        await state.update_data(new_student_id=new_student_id)

        # Предлагаем скопировать расписание
        await message.answer(
            f"✅ Ученик {name} успешно добавлен (ID: {new_student_id})\n\n"
            "Хотите скопировать расписание от другого ученика?\n"
            "Введите имя ученика, от которого копировать, или 'нет' чтобы пропустить:",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Нет")]],
                resize_keyboard=True
            )
        )

        # Устанавливаем состояние ожидания имени ученика для копирования
        await state.set_state(StudentStates.waiting_for_schedule_source)

    except ValueError as e:
        await message.answer(f"Ошибка в данных: {str(e)}\nПопробуйте еще раз.")
    except Exception as e:
        await message.answer(f"Ошибка при сохранении: {str(e)}")
        print(f"Error saving student: {str(e)}")
        await state.clear()


@create_user_router.message(StudentStates.waiting_for_schedule_source, F.text)
async def process_schedule_copy(message: Message, state: FSMContext):
    if message.text.lower() == 'нет':
        await message.answer(
            "Расписание не скопировано",
            reply_markup=await main_kb(message.from_user.id)
        )
        await state.clear()
        return

    try:
        # Получаем данные из состояния
        data = await state.get_data()
        new_student_id = data['new_student_id']

        # Ищем ученика для копирования расписания
        source_student = await execute_raw_sql(
            f"SELECT id FROM {schema}.student WHERE name ILIKE '%{message.text}%' LIMIT 1;"
        )

        if not source_student:
            await message.answer("Ученик не найден. Попробуйте еще раз или введите 'нет'")
            return

        source_student_id = source_student[0]['id']

        # Копируем расписание
        await execute_raw_sql(
            f"""
            INSERT INTO {schema}.student_schedule (student, schedule)
            SELECT {new_student_id}, schedule 
            FROM {schema}.student_schedule 
            WHERE student = {source_student_id};
            """
        )

        # Получаем количество скопированных занятий
        count_result = await execute_raw_sql(
            f"SELECT COUNT(*) FROM {schema}.student_schedule WHERE student = {new_student_id};"
        )
        count = count_result[0]['count']

        await message.answer(
            f"✅ Скопировано {count} занятий от ученика ID {source_student_id}",
            reply_markup=main_kb(message.from_user.id)
        )

    except Exception as e:
        await message.answer(f"Ошибка при копировании расписания: {str(e)}")
        print(f"Error copying schedule: {str(e)}")
    finally:
        await state.clear()


@create_user_router.message(F.text == "Отмена")
async def cancel_handler(message: Message):
    await message.answer("Действие отменено", reply_markup=main_kb(message.from_user.id))