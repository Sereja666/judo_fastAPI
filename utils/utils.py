from datetime import date, datetime
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



async def get_belt_emoji(rang_id: int) -> str:
    """Получает эмодзи пояса по ID из таблицы belt_color"""
    if not rang_id:
        return "⚪️"  # По умолчанию белый пояс

    try:
        # Получаем эмодзи пояса напрямую из базы
        from db_handler.db_funk import execute_raw_sql
        belt_data = await execute_raw_sql(
            "SELECT color FROM public.belt_color WHERE id = $1;",
            rang_id
        )

        if belt_data and belt_data[0]['color']:
            return belt_data[0]['color']
    except Exception as e:
        print(f"Error getting belt emoji: {e}")

    return "⚪️"  # По умолчанию если что-то пошло не так

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