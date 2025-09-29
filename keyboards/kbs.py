from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from create_bot import admins

# main_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='СКУД')],
#                                         # [KeyboardButton(text='Корзина')],
#                                         # [KeyboardButton(text='Контакты')],
#                                         # [KeyboardButton(text='О нас')],
#                                         [KeyboardButton(text='Броски')],
#                                         ],
#                               resize_keyboard=True,
#                               input_field_placeholder='Выберите пункт меню'
#                               )


def main_kb(user_telegram_id: int):
    kb_list = [[KeyboardButton(text="👤 Мой профиль")]]
    # if user_telegram_id in admins:
    #     kb_list.append([KeyboardButton(text="⚙️ Админ панель"),
    #                    KeyboardButton(text="Посещения")])
    # else:
    kb_list.append([KeyboardButton(text="⚙️ Админ панель"),
                    KeyboardButton(text="⚙️ Посещения"),
                    KeyboardButton(text="🥋 Новый ученик"),])
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

def home_page_kb(user_telegram_id: int):
    kb_list = [[KeyboardButton(text="🔙 Назад")]]
    if user_telegram_id in admins:
        kb_list.append([KeyboardButton(text="⚙️ Админ панель")])
    return ReplyKeyboardMarkup(
        keyboard=kb_list,
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Воспользуйтесь меню:"
    )

