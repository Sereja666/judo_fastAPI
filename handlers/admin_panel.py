from datetime import date, timedelta, datetime

from aiogram import F, Router
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import re
from create_bot import bot
from db_handler.db_funk import get_user_permissions, process_payment, execute_raw_sql
from keyboards.kbs import home_page_kb, admin_page_kb

admin_router = Router()


# Состояния для процесса оплаты
class PaymentStates(StatesGroup):
    waiting_for_payment_data = State()

# Состояния для процесса справки по болезни
class MedicalCertificateStates(StatesGroup):
    waiting_for_certificate_data = State()


@admin_router.message(F.text.endswith('Админ панель'))
async def get_profile(message: Message):
    async with ChatActionSender.typing(bot=bot, chat_id=message.from_user.id):
        admin_text = "тут текст для админа"
    await message.answer(admin_text, reply_markup=await admin_page_kb(message.from_user.id))


@admin_router.message(F.text.contains('💳 оплата'))
async def start_payment_process(message: Message, state: FSMContext):
    """Начало процесса оплаты"""
    # Проверяем права пользователя
    user_permissions = await get_user_permissions(message.from_user.id)

    if user_permissions not in [99, 2 ]:  # Только админы
        await message.answer("⛔ Доступ запрещен")
        return

    await message.answer(
        "💳 Процесс оплаты\n\n"
        "Введите данные в формате:\n"
        "<b>ФИО Сумма</b>\n\n"
        "Например:\n"
        "<code>Аносова Кира 3800</code>\n\n"
        "Или:\n"
        "<code>Иванов Петр 5000</code>",
        reply_markup=await home_page_kb(message.from_user.id)
    )
    await state.set_state(PaymentStates.waiting_for_payment_data)


@admin_router.message(PaymentStates.waiting_for_payment_data)
async def process_payment_input(message: Message, state: FSMContext):
    """Обработка введенных данных об оплате"""
    try:
        input_text = message.text.strip()

        # Разбираем ввод - последнее число это сумма, остальное ФИО
        parts = input_text.split()
        if len(parts) < 2:
            await message.answer("❌ Неверный формат. Пример: <code>Аносова Кира 3800</code>")
            return

        # Сумма - последний элемент
        amount_str = parts[-1]
        # ФИО - все кроме последнего
        student_name = ' '.join(parts[:-1])

        # Проверяем что сумма - число
        try:
            amount = int(amount_str)
        except ValueError:
            await message.answer("❌ Сумма должна быть числом. Пример: <code>Аносова Кира 3800</code>")
            return

        # Сначала поищем всех возможных кандидатов
        possible_students = await execute_raw_sql(
            f"""SELECT id, name 
            FROM public.student 
            WHERE active = true 
            AND name ILIKE $1
            LIMIT 5;""",
            f"%{student_name}%"
        )

        # Если нашли несколько кандидатов, покажем их
        if len(possible_students) > 1:
            students_list = "\n".join([f"• {s['name']}" for s in possible_students])
            await message.answer(
                f"🔍 Найдено несколько учеников по запросу '{student_name}':\n\n"
                f"{students_list}\n\n"
                f"Уточните ФИО ученика:",
                reply_markup=await home_page_kb(message.from_user.id)
            )
            return
        elif len(possible_students) == 0:
            await message.answer(
                f"❌ Ученик '{student_name}' не найден.\n"
                f"Проверьте правильность написания ФИО.",
                reply_markup=await home_page_kb(message.from_user.id)
            )
            return

        # Обрабатываем оплату для найденного ученика
        result = await process_payment(student_name, amount)

        if result["success"]:
            response_text = (
                f"✅ Оплата успешно обработана!\n\n"
                f"👤 Ученик: <b>{result['student_name']}</b>\n"
                f"💳 Сумма: <b>{result['amount']} руб.</b>\n"
                f"🎯 Тариф: <b>{result['price_description']}</b>\n"
                f"📦 Занятий добавлено: <b>{result['classes_added']}</b>\n"
                f"📊 Остаток занятий: <b>{result['new_balance']}</b>\n"
                f"{result['price_change_info']}\n"
                f"📅 Дата: <b>{result['payment_date']}</b>"
            )
        else:
            response_text = f"❌ Ошибка: {result['error']}"

        await message.answer(response_text)
        await state.clear()

    except Exception as e:
        await message.answer(f"❌ Произошла ошибка: {str(e)}")
        await state.clear()


@admin_router.message(F.text.contains('🏥 справка по болезни'))
async def start_medical_certificate_process(message: Message, state: FSMContext):
    """Начало процесса обработки справки по болезни"""
    # Проверяем права пользователя
    user_permissions = await get_user_permissions(message.from_user.id)

    if user_permissions not in [99, 2]:  # Только админы
        await message.answer("⛔ Доступ запрещен")
        return

    await message.answer(
        "🏥 Обработка справки по болезни\n\n"
        "Введите данные в формате:\n"
        "<b>ФИО ДатаНачала - ДатаОкончания</b>\n\n"
        "Например:\n"
        "<code>Аносова Кира 29.10.2025 - 05.11.2025</code>\n\n",
        reply_markup=await home_page_kb(message.from_user.id)
    )
    await state.set_state(MedicalCertificateStates.waiting_for_certificate_data)


@admin_router.message(MedicalCertificateStates.waiting_for_certificate_data)
async def process_medical_certificate(message: Message, state: FSMContext):
    """Обработка введенных данных о справке"""
    try:
        input_text = message.text.strip()

        # Парсим ввод
        result = await parse_and_process_certificate(input_text)

        if result["success"]:
            response_text = (
                f"✅ Справка по болезни обработана!\n\n"
                f"👤 Ученик: <b>{result['student_name']}</b>\n"
                f"🏥 Период болезни: <b>{result['start_date']} - {result['end_date']}</b>\n"
                f"📅 Пропущено занятий: <b>{result['missed_classes']}</b>\n"
                f"📦 Возвращено занятий: <b>{result['classes_added']}</b>\n"
                f"📊 Новый остаток: <b>{result['new_balance']}</b>\n"
                f"📝 Причина: <b>Справка по болезни</b>"
            )
        else:
            response_text = f"❌ Ошибка: {result['error']}"

        await message.answer(response_text)
        await state.clear()

    except Exception as e:
        await message.answer(f"❌ Произошла ошибка: {str(e)}")
        await state.clear()


async def parse_and_process_certificate(input_text: str) -> dict:
    """
    Парсит ввод о справке и обрабатывает возврат занятий
    """
    try:
        # Парсим формат: "ФИО DD.MM.YYYY - DD.MM.YYYY"
        pattern = r'^(.+?)\s+(\d{2}\.\d{2}\.\d{4})\s*-\s*(\d{2}\.\d{2}\.\d{4})$'
        match = re.match(pattern, input_text.strip())

        if not match:
            return {"success": False, "error": "Неверный формат. Пример: Аносова Кира 29.10.2024 - 05.11.2024"}

        student_name = match.group(1).strip()
        start_date_str = match.group(2)
        end_date_str = match.group(3)

        # Преобразуем даты
        try:
            start_date = datetime.strptime(start_date_str, '%d.%m.%Y').date()
            end_date = datetime.strptime(end_date_str, '%d.%m.%Y').date()
        except ValueError:
            return {"success": False, "error": "Неверный формат даты. Используйте ДД.ММ.ГГГГ"}

        if start_date > end_date:
            return {"success": False, "error": "Дата начала не может быть позже даты окончания"}

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

        # Рассчитываем количество пропущенных занятий
        missed_classes_result = await calculate_missed_classes(student_id, start_date, end_date)

        if not missed_classes_result["success"]:
            return missed_classes_result

        missed_classes = missed_classes_result["missed_classes"]

        if missed_classes == 0:
            return {"success": False, "error": "За указанный период у ученика не было запланированных занятий"}

        # Обновляем баланс ученика
        new_balance = current_balance + missed_classes

        update_result = await execute_raw_sql(
            f"UPDATE public.student SET classes_remaining = $1 WHERE id = $2;",
            new_balance, student_id
        )

        # Записываем информацию о справке (опционально - для истории)
        try:
            await execute_raw_sql(
                f"""INSERT INTO public.medical_certificates 
                    (student_id, start_date, end_date, missed_classes, added_classes, processed_date) 
                VALUES ($1, $2, $3, $4, $5, CURRENT_DATE);""",
                student_id, start_date, end_date, missed_classes, missed_classes
            )
        except Exception as e:
            # Если таблицы medical_certificates нет, просто логируем
            print(f"Note: Could not log medical certificate: {e}")

        return {
            "success": True,
            "student_name": student['name'],
            "start_date": start_date.strftime('%d.%m.%Y'),
            "end_date": end_date.strftime('%d.%m.%Y'),
            "missed_classes": missed_classes,
            "classes_added": missed_classes,
            "new_balance": new_balance
        }

    except Exception as e:
        print(f"Error processing medical certificate: {str(e)}")
        return {"success": False, "error": f"Системная ошибка: {str(e)}"}


async def calculate_missed_classes(student_id: int, start_date: date, end_date: date) -> dict:
    """
    Рассчитывает количество пропущенных занятий за период болезни
    на основе расписания ученика
    """
    try:
        # Получаем расписание ученика
        schedule_data = await execute_raw_sql(
            f"""SELECT DISTINCT sched.day_week, sched.time_start
            FROM public.student_schedule ss
            JOIN public.schedule sched ON ss.schedule = sched.id
            WHERE ss.student = $1;""",
            student_id
        )

        if not schedule_data:
            return {"success": False, "error": "У ученика нет расписания", "missed_classes": 0}

        # Словарь для преобразования русских названий дней в числовые
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

        # Считаем количество тренировочных дней в период болезни
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
        print(f"Error calculating missed classes: {str(e)}")
        return {"success": False, "error": f"Ошибка расчета пропущенных занятий: {str(e)}", "missed_classes": 0}