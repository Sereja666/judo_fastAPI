from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db_handler.db_funk import get_user_permissions





async def main_kb(user_telegram_id: int):
    kb_list = [[KeyboardButton(text="👤 Мой профиль")]]

    # Проверяем права пользователя через базу данных
    user_permissions = await get_user_permissions(user_telegram_id)

    if user_permissions in [99, 2]:  # Админ
        kb_list.append([KeyboardButton(text="⚙️ Админ панель"),
                        KeyboardButton(text="⚙️ Посещения"),
                        KeyboardButton(text="🥋 Новый ученик")])
    else:
        kb_list.append([KeyboardButton(text="⚙️ Посещения"),
                        KeyboardButton(text="🥋 Новый ученик")])

    return ReplyKeyboardMarkup(
        keyboard=kb_list,
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Воспользуйтесь меню:"
    )


def places_kb():
    kb_list = [
        [KeyboardButton(text="🥋 ГМР")],
        [KeyboardButton(text="🥋 Сормовская"), KeyboardButton(text="🥋 Ставрапольская")],
        [KeyboardButton(text="🔙 Назад")]
    ]

    return ReplyKeyboardMarkup(
        keyboard=kb_list,
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Выберите место:"
    )


async def home_page_kb(user_telegram_id: int):
    kb_list = [[KeyboardButton(text="🔙 Назад")]]

    # Проверяем права пользователя через базу данных
    user_permissions = await get_user_permissions(user_telegram_id)

    if user_permissions == 99:  # Админ
        kb_list.append([KeyboardButton(text="⚙️ Админ панель")])

    return ReplyKeyboardMarkup(
        keyboard=kb_list,
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Воспользуйтесь меню:"
    )

async def admin_page_kb(user_telegram_id: int):
    kb_list = [
        [KeyboardButton(text="🔙 Назад")],
        [KeyboardButton(text="💳 оплата"), KeyboardButton(text="🏥 справка по болезни")],
        [KeyboardButton(text="📋 Медсправка")]  # Теперь это меню
    ]

    # Проверяем права пользователя через базу данных
    user_permissions = await get_user_permissions(user_telegram_id)

    if user_permissions == 99:  # Админ
        kb_list.append([KeyboardButton(text="⚙️ Админ панель")])

    return ReplyKeyboardMarkup(
        keyboard=kb_list,
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Воспользуйтесь меню:"
    )

def medical_certificate_kb():
    """Клавиатура для меню медицинских справок"""
    kb_list = [
        [KeyboardButton(text="➕ Добавить справку")],
        [KeyboardButton(text="👥 Справки учеников")],
        [KeyboardButton(text="🔙 Назад")]
    ]

    return ReplyKeyboardMarkup(
        keyboard=kb_list,
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Выберите действие:"
    )