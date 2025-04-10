import pytz
from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from aiogram.utils.keyboard import InlineKeyboardBuilder
from urllib.parse import quote, unquote
from create_bot import bot, db_manager
from db_handler.db_funk import get_user_data, insert_user, execute_raw_sql
from keyboards.kbs import main_kb, home_page_kb, places_kb
from utils.utils import get_refer_id, get_now_time, get_current_week_day
from aiogram.utils.chat_action import ChatActionSender
import logging
from datetime import datetime, time

logging.basicConfig(level=logging.ERROR)

user_router = Router()

universe_text = ('Чтоб получить информацию о своем профиле воспользуйся кнопкой "Мой профиль" или специальной '
                 'командой из командного меню.')


# хендлер команды старт
@user_router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    async with ChatActionSender.typing(bot=bot, chat_id=message.from_user.id):
        user_info = await get_user_data(user_id=message.from_user.id)
        # await message.answer(text=f'Айди -> {message.from_user.id}, имя -> {user_info.get("telegram_username")}', reply_markup=main_kb(message.from_user.id))
        if user_info:
            response_text = f'{user_info.get("telegram_username")}, Вижу что вы уже в моей базе данных. {universe_text}'
        else:
            await insert_user(user_data={
                'permissions': 0,
                'telegram_id': message.from_user.id,
                'telegram_username': message.from_user.full_name,
                'user_login': message.from_user.username,

                'date_reg': get_now_time()
            })

            response_text = (f'{message.from_user.full_name}, вы зарегистрированы в боте {universe_text}')

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
        text = (f'👉 Ваш телеграм ID: <code><b>{message.from_user.id}</b></code>\n'
                f'👥 Количество приглашенных тобой пользователей: <b>{user_info.get("count_refer")}</b>\n\n'
                f'🚀 Вот твоя персональная ссылка на приглашение: '
                f'<code>https://t.me/easy_refer_bot?start={message.from_user.id}</code>')
    await message.answer(text, reply_markup=home_page_kb(message.from_user.id))


# Словарь для хранения выбранных студентов {id: name}
selected_students = {}


# Обработчик кнопки "Посещения" с проверкой прав (оптимизированный)
@user_router.message(F.text.contains('Посещения'))
async def handle_visits(message: types.Message):
    try:
        # Проверяем права пользователя
        user_permission = await execute_raw_sql(
            f"SELECT permissions FROM public.telegram_user "
            f"WHERE telegram_id = {message.from_user.id};"
        )

        if user_permission and user_permission[0]['permissions'] in (1, 2, 99):
            await message.answer("Выберите место:", reply_markup=places_kb())
        else:
            await message.answer("⛔ Доступ запрещен", reply_markup=types.ReplyKeyboardRemove())

    except Exception as e:
        await message.answer("⚠️ Ошибка проверки прав доступа")
        print(f"Permission check error: {str(e)}")


@user_router.message(F.text.in_(['🥋 ГМР', '🥋 Сормовская', '🥋 Ставрапольская']))
async def handle_city_selection(message: types.Message):
    try:
        selected_place_name = message.text.replace('🥋 ', '')
        user_telegram_id = message.from_user.id

        # Получаем данные тренера по telegram_id
        trainer_data = await execute_raw_sql(
            f"""
            SELECT t.id, t.name 
            FROM public.trainer t
            WHERE t.telegram_id = {user_telegram_id};
            """
        )

        if not trainer_data:
            await message.answer("⛔ Вы не зарегистрированы как тренер")
            return

        trainer_id = trainer_data[0]['id']
        trainer_name = trainer_data[0]['name']

        # Получаем ID места тренировки
        place_data = await execute_raw_sql(
            f"SELECT id FROM public.training_place WHERE name = '{selected_place_name}';"
        )

        if not place_data:
            await message.answer("Ошибка: место тренировки не найдено")
            return

        place_id = place_data[0]['id']

        cur_time = datetime.now().strftime("%H:%M")
        week_day = get_current_week_day()

        # Получаем данные о текущем занятии
        query = f"""
        SELECT 
            s.id as schedule_id,
            s.time_start,
            s.sport_discipline as discipline_id,
            sp.name as discipline_name
        FROM public.schedule s
        JOIN public.sport sp ON s.sport_discipline = sp.id
        WHERE s.training_place = {place_id}
        AND s.day_week = '{week_day}'
        AND s.time_start <= '{cur_time}' 
        AND s.time_end >= '{cur_time}';
        """

        schedule_data = await execute_raw_sql(query)

        if not schedule_data:
            await message.answer(f"На {selected_place_name} сейчас нет активных занятий.")
            return

        schedule = schedule_data[0]

        # Получаем список студентов
        students = await execute_raw_sql(
            f"""
            SELECT st.id, st.name 
            FROM public.student_schedule ss
            JOIN public.student st ON ss.student = st.id
            WHERE ss.schedule = {schedule['schedule_id']};
            """
        )

        if not students:
            await message.answer(f"На занятии нет записанных студентов.")
            return

        # Создаем клавиатуру с кнопками студентов
        builder = InlineKeyboardBuilder()

        for student in students:
            is_selected = str(student['id']) in selected_students
            emoji = "☑️" if is_selected else "⬜️"

            builder.button(
                text=f"{emoji} {student['name']}",
                callback_data=f"student:{student['id']}"
            )

        # Добавляем кнопку подтверждения (trainer_id берем из данных тренера)
        builder.button(
            text="✅ Подтвердить посещение",
            callback_data=(
                f"confirm:{schedule['schedule_id']}:"
                f"{trainer_id}:"  # Используем ID тренера из БД
                f"{place_id}:"
                f"{schedule['discipline_id']}"
            )
        )

        builder.adjust(1)

        # Форматируем время
        start_time = schedule['time_start']
        if isinstance(start_time, time):
            start_time = start_time.strftime("%H:%M")

        await message.answer(
            f"👨‍🏫 Тренер: {trainer_name}\n"
            f"🏢 Место: {selected_place_name}\n"
            f"🕒 Время: {start_time}\n"
            f"🧘 Дисциплина: {schedule['discipline_name']}\n"
            "Выберите студентов:",
            reply_markup=builder.as_markup()
        )

    except Exception as e:
        await message.answer("⚠️ Ошибка при загрузке данных. Попробуйте позже.")
        print(f"Error in handle_city_selection: {str(e)}")


@user_router.callback_query(F.data.startswith("student:"))
async def select_student(callback: types.CallbackQuery):
    try:
        _, student_id = callback.data.split(":")

        # Создаем новую клавиатуру
        new_keyboard = []
        student_name = None

        for row in callback.message.reply_markup.inline_keyboard:
            new_row = []
            for button in row:
                if button.callback_data == callback.data:
                    # Это нажатая кнопка
                    student_name = button.text[2:]  # Убираем эмодзи
                    if student_id in selected_students:
                        del selected_students[student_id]
                        new_text = f"⬜️ {student_name}"
                    else:
                        selected_students[student_id] = student_name
                        new_text = f"☑️ {student_name}"
                    new_row.append(InlineKeyboardButton(
                        text=new_text,
                        callback_data=button.callback_data
                    ))
                else:
                    new_row.append(button)
            new_keyboard.append(new_row)

        if not student_name:
            await callback.answer("Студент не найден", show_alert=True)
            return

        # Обновляем сообщение
        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(inline_keyboard=new_keyboard)
        )
        await callback.answer()

    except Exception as e:
        await callback.answer("Ошибка при выборе", show_alert=True)
        print(f"Error in select_student: {str(e)}")


@user_router.callback_query(F.data.startswith("confirm:"))
async def confirm_attendance(callback: types.CallbackQuery):
    try:
        if not selected_students:
            await callback.answer("Выберите хотя бы одного студента!", show_alert=True)
            return

        # Парсим параметры (trainer_id теперь берется из БД)
        _, schedule_id, trainer_id, place_id, discipline_id = callback.data.split(":")

        # Получаем данные тренера для отчета
        trainer_data = await execute_raw_sql(
            f"SELECT name FROM public.trainer WHERE id = {trainer_id};"
        )
        trainer_name = trainer_data[0]['name'] if trainer_data else f"Тренер #{trainer_id}"

        # Получаем московское время
        moscow_tz = pytz.timezone('Europe/Moscow')
        now_moscow = datetime.now(moscow_tz)
        current_date = now_moscow.date()

        # Получаем время занятия из расписания
        schedule_data = await execute_raw_sql(
            f"SELECT time_start FROM public.schedule WHERE id = {schedule_id};"
        )

        if not schedule_data:
            await callback.answer("Ошибка: расписание не найдено", show_alert=True)
            return

        visit_time = schedule_data[0]['time_start']
        visit_datetime = datetime.combine(current_date, visit_time).astimezone(moscow_tz)

        # Получаем название места для отчета
        place_data = await execute_raw_sql(
            f"SELECT name FROM public.training_place WHERE id = {place_id};"
        )
        place_name = place_data[0]['name'] if place_data else f"Место #{place_id}"

        # Сохраняем посещения
        success_count = 0
        skipped_count = 0
        errors = []

        for student_id in selected_students.keys():
            try:
                # Проверяем существование записи
                existing = await execute_raw_sql(
                    f"SELECT id FROM public.visit "
                    f"WHERE student = {student_id} "
                    f"AND shedule = {schedule_id} "
                    f"AND DATE(data) = '{current_date}';"
                )

                if existing:
                    skipped_count += 1
                    continue

                # Создаем новую запись с place_id
                await execute_raw_sql(
                    f"INSERT INTO public.visit ("
                    f"data, trainer, student, place, sport_discipline, shedule"
                    f") VALUES ("
                    f"'{visit_datetime.isoformat()}', "
                    f"{trainer_id}, "
                    f"{student_id}, "
                    f"{place_id}, "  # Используем place_id
                    f"{discipline_id}, "
                    f"{schedule_id}"
                    f");"
                )
                success_count += 1
            except Exception as e:
                errors.append(f"Студент {student_id}: {str(e)}")

        # Формируем отчет с названием места
        report_lines = [
            f"📊 Результат сохранения:",
            f"📅 Дата: {current_date.strftime('%d.%m.%Y')}",
            f"⏱ Время: {visit_time.strftime('%H:%M')}",
            f"🏢 Место: {place_name}",
            f"✅ Новые записи: {success_count}",
            f"⏩ Пропущено дублей: {skipped_count}",
            f"❌ Ошибки: {len(errors)}",
            "👥 Список:"
        ]
        report_lines.extend(f"• {name}" for name in selected_students.values())

        if errors:
            report_lines.append("\nОшибки:")
            report_lines.extend(errors[:3])

        await callback.message.answer("\n".join(report_lines))
        selected_students.clear()
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer()

    except Exception as e:
        await callback.answer("Критическая ошибка!", show_alert=True)
        print(f"Error in confirm_attendance: {str(e)}")