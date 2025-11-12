from datetime import date, timedelta, datetime

from aiogram import F, Router
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, ReplyKeyboardMarkup, \
    KeyboardButton
from aiogram.utils.chat_action import ChatActionSender
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import re
from create_bot import bot
from db_handler.db_funk import get_user_permissions, process_payment, execute_raw_sql, get_student_certificates, \
    get_all_certificates
from keyboards.kbs import home_page_kb, admin_page_kb, medical_certificate_kb

admin_router = Router()


# Состояния для процесса оплаты
class PaymentStates(StatesGroup):
    waiting_for_payment_data = State()


# Состояния для медицинских справок
class MedicalCertificateStates(StatesGroup):
    waiting_for_action = State()
    waiting_for_student_name = State()
    waiting_for_certificate_type = State()
    waiting_for_certificate_dates = State()  # Для справок по болезни
    waiting_for_certificate_dates_dopusk = State()  # НОВОЕ: для меддопусков
    waiting_for_student_for_list = State()


@admin_router.message(F.text.endswith('Админ панель'))
async def get_profile(message: Message):
    """Главное меню админ панели"""
    async with ChatActionSender.typing(bot=bot, chat_id=message.from_user.id):
        admin_text = "Добро пожаловать в админ панель!"
    await message.answer(admin_text, reply_markup=await admin_page_kb(message.from_user.id))


@admin_router.message(F.text.contains('💳 оплата'))
async def start_payment_process(message: Message, state: FSMContext):
    """Начало процесса оплаты"""
    user_permissions = await get_user_permissions(message.from_user.id)

    if user_permissions not in [99, 2]:
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
        parts = input_text.split()

        if len(parts) < 2:
            await message.answer("❌ Неверный формат. Пример: <code>Аносова Кира 3800</code>")
            return

        amount_str = parts[-1]
        student_name = ' '.join(parts[:-1])

        try:
            amount = int(amount_str)
        except ValueError:
            await message.answer("❌ Сумма должна быть числом. Пример: <code>Аносова Кира 3800</code>")
            return

        # Поиск ученика
        possible_students = await execute_raw_sql(
            """SELECT id, name 
            FROM public.student 
            WHERE active = true 
            AND name ILIKE $1
            LIMIT 5;""",
            f"%{student_name}%"
        )

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

        # Обработка оплаты
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
    """Начало процесса обработки справки по болезни (возврат занятий)"""
    user_permissions = await get_user_permissions(message.from_user.id)

    if user_permissions not in [99, 2]:
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
    await state.set_state(MedicalCertificateStates.waiting_for_certificate_dates)


@admin_router.message(MedicalCertificateStates.waiting_for_certificate_dates)
async def process_medical_certificate(message: Message, state: FSMContext):
    """Обработка введенных данных о справке по болезни"""
    try:
        input_text = message.text.strip()
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
    """Парсит ввод о справке по болезни и обрабатывает возврат занятий"""
    try:
        pattern = r'^(.+?)\s+(\d{2}\.\d{2}\.\d{4})\s*-\s*(\d{2}\.\d{2}\.\d{4})$'
        match = re.match(pattern, input_text.strip())

        if not match:
            return {"success": False, "error": "Неверный формат. Пример: Аносова Кира 29.10.2024 - 05.11.2024"}

        student_name = match.group(1).strip()
        start_date_str = match.group(2)
        end_date_str = match.group(3)

        try:
            start_date = datetime.strptime(start_date_str, '%d.%m.%Y').date()
            end_date = datetime.strptime(end_date_str, '%d.%m.%Y').date()
        except ValueError:
            return {"success": False, "error": "Неверный формат даты. Используйте ДД.ММ.ГГГГ"}

        if start_date > end_date:
            return {"success": False, "error": "Дата начала не может быть позже даты окончания"}

        # Ищем ученика
        student_data = await execute_raw_sql(
            """SELECT id, name, classes_remaining 
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

        await execute_raw_sql(
            "UPDATE public.student SET classes_remaining = $1 WHERE id = $2;",
            new_balance, student_id
        )

        # Записываем информацию о справке в историю
        try:
            await execute_raw_sql(
                """INSERT INTO public.medical_certificates 
                    (student_id, start_date, end_date, missed_classes, added_classes, processed_date) 
                VALUES ($1, $2, $3, $4, $5, CURRENT_DATE);""",
                student_id, start_date, end_date, missed_classes, missed_classes
            )
        except Exception as e:
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
    """Рассчитывает количество пропущенных занятий за период болезни"""
    try:
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
        print(f"Error calculating missed classes: {str(e)}")
        return {"success": False, "error": f"Ошибка расчета пропущенных занятий: {str(e)}", "missed_classes": 0}


# ===== МЕНЮ МЕДИЦИНСКИХ СПРАВОК =====

@admin_router.message(F.text.contains('📋 Медсправка'))
async def medical_certificate_menu(message: Message, state: FSMContext):
    """Меню медицинских справок (допусков)"""
    user_permissions = await get_user_permissions(message.from_user.id)

    if user_permissions not in [99, 2]:
        await message.answer("⛔ Доступ запрещен")
        return

    await message.answer(
        "📋 Медицинские справки\n\n"
        "Выберите действие:",
        reply_markup=medical_certificate_kb()
    )
    await state.set_state(MedicalCertificateStates.waiting_for_action)


@admin_router.message(MedicalCertificateStates.waiting_for_action, F.text.contains('➕ Добавить справку'))
async def start_add_certificate(message: Message, state: FSMContext):
    """Начало процесса добавления новой справки"""
    await message.answer(
        "➕ Добавление медицинской справки\n\n"
        "Введите ФИО ученика:\n\n"
        "Например:\n"
        "<code>Аносова Кира</code>",
        reply_markup=await home_page_kb(message.from_user.id)
    )
    await state.set_state(MedicalCertificateStates.waiting_for_student_name)


@admin_router.message(MedicalCertificateStates.waiting_for_student_name)
async def process_student_name_for_certificate(message: Message, state: FSMContext):
    """Обработка введенного имени ученика для медсправки"""
    try:
        student_name = message.text.strip()

        student_data = await execute_raw_sql(
            """SELECT id, name 
            FROM public.student 
            WHERE active = true 
            AND name ILIKE $1
            LIMIT 5;""",
            f"%{student_name}%"
        )

        if not student_data:
            await message.answer(
                f"❌ Ученик '{student_name}' не найден.\n"
                f"Проверьте правильность написания ФИО.",
                reply_markup=await home_page_kb(message.from_user.id)
            )
            await state.clear()
            return

        if len(student_data) > 1:
            students_list = "\n".join([f"• {s['name']}" for s in student_data])
            await message.answer(
                f"🔍 Найдено несколько учеников по запросу '{student_name}':\n\n"
                f"{students_list}\n\n"
                f"Уточните ФИО ученика:",
                reply_markup=await home_page_kb(message.from_user.id)
            )
            return

        student = student_data[0]
        await state.update_data(
            student_id=student['id'],
            student_name=student['name']
        )

        cert_types = await execute_raw_sql(
            "SELECT id, name_cert FROM public.medcertificat_type ORDER BY id;"
        )

        if not cert_types:
            await message.answer(
                "❌ В системе не настроены типы медицинских справок.",
                reply_markup=await home_page_kb(message.from_user.id)
            )
            await state.clear()
            return

        await state.update_data(cert_types=cert_types)


        builder = InlineKeyboardBuilder()

        for cert_type in cert_types:
            builder.button(
                text=f"⬜️ {cert_type['name_cert']}",
                callback_data=f"cert_type:{cert_type['id']}"
            )

        builder.button(
            text="✅ Продолжить",
            callback_data="cert_continue"
        )

        builder.adjust(1)

        await message.answer(
            f"👤 Ученик: <b>{student['name']}</b>\n\n"
            "Выберите тип медицинской справки:",
            reply_markup=builder.as_markup()
        )
        await state.set_state(MedicalCertificateStates.waiting_for_certificate_type)

    except Exception as e:
        await message.answer(f"❌ Произошла ошибка: {str(e)}")
        await state.clear()


@admin_router.callback_query(MedicalCertificateStates.waiting_for_certificate_type, F.data.startswith("cert_type:"))
async def select_certificate_type(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора типа справки"""
    try:
        _, cert_type_id = callback.data.split(":")
        cert_type_id = int(cert_type_id)

        data = await state.get_data()
        cert_types = data.get('cert_types', [])

        new_keyboard = []
        for cert_type in cert_types:
            if cert_type['id'] == cert_type_id:
                new_keyboard.append([InlineKeyboardButton(
                    text=f"✅ {cert_type['name_cert']}",
                    callback_data=f"cert_type:{cert_type['id']}"
                )])
                await state.update_data(selected_cert_type_id=cert_type_id)
            else:
                new_keyboard.append([InlineKeyboardButton(
                    text=f"⬜️ {cert_type['name_cert']}",
                    callback_data=f"cert_type:{cert_type['id']}"
                )])

        new_keyboard.append([InlineKeyboardButton(
            text="✅ Продолжить",
            callback_data="cert_continue"
        )])

        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(inline_keyboard=new_keyboard)
        )
        await callback.answer()

    except Exception as e:
        await callback.answer("❌ Ошибка при выборе типа справки", show_alert=True)


@admin_router.callback_query(MedicalCertificateStates.waiting_for_certificate_type, F.data == "cert_continue")
async def continue_to_dates(callback: CallbackQuery, state: FSMContext):
    """Переход к вводу дат справки"""
    try:
        data = await state.get_data()

        if 'selected_cert_type_id' not in data:
            await callback.answer("❌ Выберите тип справки", show_alert=True)
            return

        await callback.message.edit_reply_markup(reply_markup=None)

        await callback.message.answer(
            f"👤 Ученик: <b>{data['student_name']}</b>\n\n"
            "Введите даты действия справки в формате:\n"
            "<b>ДД.ММ.ГГГГ - ДД.ММ.ГГГГ</b>\n\n"
            "Например:\n"
            "<code>11.12.2025 - 31.12.2026</code>",
            reply_markup=await home_page_kb(callback.from_user.id)
        )

        # ИЗМЕНЕНИЕ: используем новое состояние для допусков
        await state.set_state(MedicalCertificateStates.waiting_for_certificate_dates_dopusk)
        await callback.answer()

    except Exception as e:
        await callback.answer("❌ Ошибка", show_alert=True)


@admin_router.message(MedicalCertificateStates.waiting_for_certificate_dates)
async def process_certificate_dates(message: Message, state: FSMContext):
    """Обработка введенных дат справки (допуска)"""
    try:
        input_text = message.text.strip()
        data = await state.get_data()

        result = await parse_and_save_certificate(
            data['student_id'],
            data['selected_cert_type_id'],
            input_text
        )

        if result["success"]:
            cert_type_name = await execute_raw_sql(
                "SELECT name_cert FROM public.medcertificat_type WHERE id = $1;",
                data['selected_cert_type_id']
            )

            cert_name = cert_type_name[0]['name_cert'] if cert_type_name else "Неизвестный тип"

            response_text = (
                f"✅ Медицинская справка успешно добавлена!\n\n"
                f"👤 Ученик: <b>{data['student_name']}</b>\n"
                f"🏥 Тип справки: <b>{cert_name}</b>\n"
                f"📅 Период действия: <b>{result['start_date']} - {result['end_date']}</b>\n"
                f"🆔 ID записи: <b>{result['record_id']}</b>"
            )
        else:
            response_text = f"❌ Ошибка: {result['error']}"

        await message.answer(response_text)
        await state.clear()

    except Exception as e:
        await message.answer(f"❌ Произошла ошибка: {str(e)}")
        await state.clear()


# Добавьте новый обработчик для дат допусков:
@admin_router.message(MedicalCertificateStates.waiting_for_certificate_dates_dopusk)
async def process_certificate_dates_dopusk(message: Message, state: FSMContext):
    """Обработка введенных дат справки (допуска)"""
    try:
        input_text = message.text.strip()
        data = await state.get_data()

        result = await parse_and_save_certificate(
            data['student_id'],
            data['selected_cert_type_id'],
            input_text
        )

        if result["success"]:
            cert_type_name = await execute_raw_sql(
                "SELECT name_cert FROM public.medcertificat_type WHERE id = $1;",
                data['selected_cert_type_id']
            )

            cert_name = cert_type_name[0]['name_cert'] if cert_type_name else "Неизвестный тип"

            response_text = (
                f"✅ Медицинская справка успешно добавлена!\n\n"
                f"👤 Ученик: <b>{data['student_name']}</b>\n"
                f"🏥 Тип справки: <b>{cert_name}</b>\n"
                f"📅 Период действия: <b>{result['start_date']} - {result['end_date']}</b>\n"
                f"🆔 ID записи: <b>{result['record_id']}</b>"
            )
        else:
            response_text = f"❌ Ошибка: {result['error']}"

        await message.answer(response_text)
        await state.clear()

    except Exception as e:
        await message.answer(f"❌ Произошла ошибка: {str(e)}")
        await state.clear()

async def parse_and_save_certificate(student_id: int, cert_type_id: int, input_text: str) -> dict:
    """Парсит даты и сохраняет медицинскую справку (допуск)"""
    try:
        pattern = r'^(\d{2}\.\d{2}\.\d{4})\s*-\s*(\d{2}\.\d{2}\.\d{4})$'
        match = re.match(pattern, input_text.strip())

        if not match:
            return {"success": False, "error": "Неверный формат. Пример: 01.12.2024 - 31.12.2024"}

        start_date_str = match.group(1)
        end_date_str = match.group(2)

        try:
            start_date = datetime.strptime(start_date_str, '%d.%m.%Y').date()
            end_date = datetime.strptime(end_date_str, '%d.%m.%Y').date()
        except ValueError:
            return {"success": False, "error": "Неверный формат даты. Используйте ДД.ММ.ГГГГ"}

        if start_date > end_date:
            return {"success": False, "error": "Дата начала не может быть позже даты окончания"}

        existing_cert = await execute_raw_sql(
            """SELECT id 
            FROM public.medcertificat_received 
            WHERE student_id = $1 
            AND cert_id = $2 
            AND active = true
            AND (
                (date_start <= $3 AND date_end >= $3) OR
                (date_start <= $4 AND date_end >= $4) OR
                (date_start >= $3 AND date_end <= $4)
            )
            LIMIT 1;""",
            student_id, cert_type_id, start_date, end_date
        )

        if existing_cert:
            return {"success": False, "error": "У ученика уже есть активная справка этого типа на указанный период"}

        result = await execute_raw_sql(
            """INSERT INTO public.medcertificat_received 
                (student_id, cert_id, date_start, date_end, active) 
            VALUES ($1, $2, $3, $4, true)
            RETURNING id;""",
            student_id, cert_type_id, start_date, end_date
        )

        if not result:
            return {"success": False, "error": "Ошибка при сохранении в базу данных"}

        return {
            "success": True,
            "record_id": result[0]['id'],
            "start_date": start_date.strftime('%d.%m.%Y'),
            "end_date": end_date.strftime('%d.%m.%Y')
        }

    except Exception as e:
        print(f"Error saving medical certificate: {str(e)}")
        return {"success": False, "error": f"Системная ошибка: {str(e)}"}


@admin_router.message(MedicalCertificateStates.waiting_for_action, F.text.contains('👥 Справки учеников'))
async def start_view_certificates(message: Message, state: FSMContext):
    """Начало процесса просмотра справок учеников"""
    await message.answer(
        "👥 Просмотр медицинских справок\n\n"
        "Введите ФИО ученика для просмотра его справок:\n\n"
        "Например:\n"
        "<code>Аносова Кира</code>\n\n"
        "Или нажмите '📋 Все справки' для полного списка",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📋 Все справки")],
                [KeyboardButton(text="🔙 Назад")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )
    await state.set_state(MedicalCertificateStates.waiting_for_student_for_list)


@admin_router.message(MedicalCertificateStates.waiting_for_action, F.text.contains('🔙 Назад'))
async def back_to_main_menu(message: Message, state: FSMContext):
    """Возврат в главное меню"""
    await message.answer("Возврат в главное меню", reply_markup=await admin_page_kb(message.from_user.id))
    await state.clear()


@admin_router.message(MedicalCertificateStates.waiting_for_student_for_list, F.text.contains('📋 Все справки'))
async def show_all_certificates(message: Message, state: FSMContext):
    """Показывает все медицинские справки"""
    try:
        certificates = await get_all_certificates()

        if not certificates:
            await message.answer("❌ В системе нет медицинских справок.")
            await state.clear()
            return

        students_certs = {}
        for cert in certificates:
            student_name = cert['student_name']
            if student_name not in students_certs:
                students_certs[student_name] = []
            students_certs[student_name].append(cert)

        message_text = "📋 Все медицинские справки:\n\n"

        for student_name, certs in students_certs.items():
            message_text += f"👤 <b>{student_name}</b>:\n"

            for cert in certs:
                status_icon = "✅" if cert['status'] == 'active' else "❌" if cert['status'] == 'expired' else "🚫"
                status_text = "Активная" if cert['status'] == 'active' else "Просрочена" if cert[
                                                                                                'status'] == 'expired' else "Неактивна"

                message_text += (
                    f"  {status_icon} <b>{cert['certificate_type']}</b>\n"
                    f"     📅 {cert['start_date']} - {cert['end_date']} ({status_text})\n"
                )

            message_text += "\n"

        if len(message_text) > 4000:
            parts = [message_text[i:i + 4000] for i in range(0, len(message_text), 4000)]
            for part in parts:
                await message.answer(part)
        else:
            await message.answer(message_text)

        await state.clear()

    except Exception as e:
        await message.answer(f"❌ Ошибка при получении списка справок: {str(e)}")
        await state.clear()


@admin_router.message(MedicalCertificateStates.waiting_for_student_for_list)
async def show_student_certificates(message: Message, state: FSMContext):
    """Показывает медицинские справки конкретного ученика"""
    try:
        student_name = message.text.strip()

        student_data = await execute_raw_sql(
            """SELECT id, name 
            FROM public.student 
            WHERE active = true 
            AND name ILIKE $1
            LIMIT 5;""",
            f"%{student_name}%"
        )

        if not student_data:
            await message.answer(
                f"❌ Ученик '{student_name}' не найден.\n"
                f"Проверьте правильность написания ФИО.",
                reply_markup=medical_certificate_kb()
            )
            await state.set_state(MedicalCertificateStates.waiting_for_action)
            return

        if len(student_data) > 1:
            students_list = "\n".join([f"• {s['name']}" for s in student_data])
            await message.answer(
                f"🔍 Найдено несколько учеников по запросу '{student_name}':\n\n"
                f"{students_list}\n\n"
                f"Уточните ФИО ученика:",
                reply_markup=medical_certificate_kb()
            )
            return

        student = student_data[0]
        certificates = await get_student_certificates(student['id'])

        if not certificates:
            await message.answer(
                f"❌ У ученика <b>{student['name']}</b> нет медицинских справок.",
                reply_markup=medical_certificate_kb()
            )
            await state.set_state(MedicalCertificateStates.waiting_for_action)
            return

        message_text = f"📋 Медицинские справки ученика <b>{student['name']}</b>:\n\n"

        for cert in certificates:
            status_icon = "✅" if cert['status'] == 'active' else "❌" if cert['status'] == 'expired' else "🚫"
            status_text = "Активная" if cert['status'] == 'active' else "Просрочена" if cert[
                                                                                            'status'] == 'expired' else "Неактивна"
            days_info = cert['days_info']

            message_text += (
                f"{status_icon} <b>{cert['certificate_type']}</b>\n"
                f"📅 {cert['start_date']} - {cert['end_date']}\n"
                f"📊 {status_text} • {days_info}\n"
                f"🆔 ID: {cert['record_id']}\n\n"
            )

        await message.answer(message_text, reply_markup=medical_certificate_kb())
        await state.set_state(MedicalCertificateStates.waiting_for_action)

    except Exception as e:
        await message.answer(f"❌ Ошибка при получении справок: {str(e)}")
        await state.clear()


async def record_extra_student_visit(student_name: str, trainer_telegram_id: int,
                                     schedule_id: int = None, place_id: int = None,
                                     discipline_id: int = None) -> dict:
    """Записывает ученика на тренировку не по расписанию"""
    try:
        student_data = await execute_raw_sql(
            """SELECT id, name, classes_remaining 
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

        trainer_data = await execute_raw_sql(
            """SELECT id, name 
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

        current_datetime_data = await execute_raw_sql("SELECT NOW() as current_datetime;")
        current_datetime = current_datetime_data[0]['current_datetime']
        current_date = current_datetime.date()
        current_time = current_datetime.time()

        today_visits = await execute_raw_sql(
            """SELECT COUNT(*) as visit_count 
            FROM public.visit 
            WHERE student = $1 
            AND DATE(data) = $2;""",
            student_id, current_date
        )

        visit_count = today_visits[0]['visit_count'] if today_visits else 0
        class_deducted = False
        new_balance = current_balance

        if visit_count == 0 and current_balance > 0:
            new_balance = current_balance - 1
            class_deducted = True

            await execute_raw_sql(
                "UPDATE public.student SET classes_remaining = $1 WHERE id = $2;",
                new_balance, student_id
            )

        if not place_id:
            place_data = await execute_raw_sql(
                "SELECT id, name FROM public.training_place LIMIT 1;"
            )
            if not place_data:
                return {"success": False, "error": "Не найдены места тренировок"}
            place = place_data[0]
            place_id = place['id']
        else:
            place_data = await execute_raw_sql(
                "SELECT id, name FROM public.training_place WHERE id = $1;",
                place_id
            )
            if not place_data:
                return {"success": False, "error": "Указанное место тренировки не найдено"}
            place = place_data[0]

        if not discipline_id:
            sport_data = await execute_raw_sql(
                "SELECT id, name FROM public.sport LIMIT 1;"
            )
            sport_id = sport_data[0]['id'] if sport_data else 1
            sport_name = sport_data[0]['name'] if sport_data else "Неизвестная дисциплина"
        else:
            sport_data = await execute_raw_sql(
                "SELECT id, name FROM public.sport WHERE id = $1;",
                discipline_id
            )
            if sport_data:
                sport_id = sport_data[0]['id']
                sport_name = sport_data[0]['name']
            else:
                sport_id = discipline_id
                sport_name = "Неизвестная дисциплина"

        visit_result = await execute_raw_sql(
            """INSERT INTO public.visit 
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