from datetime import datetime
import pytz
import locale
from decimal import Decimal
from typing import Any, Union

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
    return day_of_week.lower()

    # Функция для определения эмодзи по цвету пояса


def get_belt_emoji(rang):
    if not rang:
        return "⬜"  # Белый по умолчанию

    rang_lower = rang.lower()

    # Словарь соответствия цветов поясов и эмодзи
    belt_colors = {
        "бел": "⬜",  # Белый пояс
        "желт": "🟨",  # Желтый пояс
        "жёлт": "🟨",  # Желтый пояс
        "оранж": "🟧",  # Оранжевый пояс
        "зелен": "🟩",  # Зеленый пояс
        "зелён": "🟩",  # Зеленый пояс
        "син": "🟦",  # Синий пояс
        "фиолет": "🟪",  # Фиолетовый пояс
        "коричн": "🟫",  # Коричневый пояс
        "красн": "🟥",  # Красный пояс
        "черн": "⬛",  # Черный пояс
        "чёрн": "⬛"  # Черный пояс
    }

    # Ищем соответствие в словаре
    for color_key, emoji in belt_colors.items():
        if color_key in rang_lower:
            return emoji

    return "⬜"  # По умолчанию белый


def convert_to_serializable(data: Any) -> Any:
    """
    Преобразует данные в JSON-сериализуемый формат для Redis FSM.

    Args:
        data: Любые данные для преобразования

    Returns:
        JSON-сериализуемые данные
    """
    if data is None:
        return None

    # Обработка списков и кортежей
    if isinstance(data, (list, tuple)):
        return [convert_to_serializable(item) for item in data]

    # Обработка словарей
    elif isinstance(data, dict):
        return {str(key): convert_to_serializable(value) for key, value in data.items()}

    # Обработка объектов Record (asyncpg) и namedtuple
    elif hasattr(data, '_asdict'):
        return convert_to_serializable(data._asdict())

    # Обработка обычных объектов
    elif hasattr(data, '__dict__') and not isinstance(data, type):
        return convert_to_serializable(data.__dict__)

    # Обработка специфических типов данных
    elif isinstance(data, (datetime, date)):
        return data.isoformat()

    elif isinstance(data, Decimal):
        return float(data)

    # Базовые типы, которые уже сериализуемы
    elif isinstance(data, (int, float, str, bool)):
        return data

    # Для всех остальных типов используем строковое представление
    else:
        return str(data)


def prepare_state_data(**kwargs) -> dict:
    """
    Подготавливает данные для сохранения в состоянии FSM.

    Args:
        **kwargs: Произвольные именованные параметры

    Returns:
        Словарь с сериализуемыми данными
    """
    return {key: convert_to_serializable(value) for key, value in kwargs.items()}