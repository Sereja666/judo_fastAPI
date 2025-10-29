from aiogram import F, Router
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from create_bot import bot
from db_handler.db_funk import get_user_permissions, process_payment, execute_raw_sql
from keyboards.kbs import home_page_kb, admin_page_kb

admin_router = Router()


# Состояния для процесса оплаты
class PaymentStates(StatesGroup):
    waiting_for_payment_data = State()


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

    if user_permissions != 99:  # Только админы
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