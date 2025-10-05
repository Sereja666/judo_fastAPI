from datetime import datetime
import pytz
import locale


def get_now_time():
    now = datetime.now(pytz.timezone('Europe/Moscow'))
    # Convert to naive datetime
    return now.replace(tzinfo=None)


# достаем refer_id из команды /start
def get_refer_id(command_args):
    try:
        return int(command_args)
    except (TypeError, ValueError):
        return None

def get_current_week_day():
    # Получаем текущую дату
    now = datetime.now()
    # Устанавливаем локаль на русский язык
    # locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
    locale.setlocale(locale.LC_TIME, 'ru_RU')
    # Получаем день недели в виде строки
    day_of_week = now.strftime("%A")  # Полное название дня недели
    # day_of_week = now.strftime("%a")  # Сокращенное название дня недели
    return day_of_week

    # Функция для определения эмодзи по цвету пояса


def get_belt_emoji(rang):
    if not rang:
        return "⬜"  # Белый по умолчанию

    rang_lower = rang.lower()

    # Словарь соответствия цветов поясов и эмодзи
    belt_colors = {
        "бел": "⬜",  # Белый пояс
        "желт": "🟨",  # Желтый пояс
        "оранж": "🟧",  # Оранжевый пояс
        "зелен": "🟩",  # Зеленый пояс
        "син": "🟦",  # Синий пояс
        "фиолет": "🟪",  # Фиолетовый пояс
        "коричн": "🟫",  # Коричневый пояс
        "красн": "🟥",  # Красный пояс
        "черн": "⬛"  # Черный пояс
    }

    # Ищем соответствие в словаре
    for color_key, emoji in belt_colors.items():
        if color_key in rang_lower:
            return emoji

    return "⬜"  # По умолчанию белый