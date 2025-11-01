#!/usr/bin/env python3
"""
Ежедневное вычитание занятий за посещения
Запускается через cron каждый день в 23:00

## Открыть crontab для редактирования
crontab -e

# Добавить строку (запуск каждый день в 23:00)
0 23 * * * /app/judo_fastAPI/handlers/daily_attendance.py

# Или с логированием в отдельный файл
0 23 * * * /app/judo_fastAPI/handlers/daily_attendance.py >> /var/log/daily_attendance_cron.log 2>&1
chmod +x /app/judo_fastAPI/handlers/daily_attendance.py
Прямой запуск
python3 /app/judo_fastAPI/handlers/daily_attendance.py

# Или через cron вручную (если настроен)
/app/judo_fastAPI/handlers/daily_attendance.py
Просмотр логов
tail -f /var/log/daily_attendance.log

# Проверка cron логов
grep CRON /var/log/syslog

# Проверка выполнения
grep "ОБНОВЛЕНО" /var/log/daily_attendance.log
"""
#!/usr/bin/env python3
"""
Ежедневное вычитание занятий за посещения и расчет даты следующей оплаты
Запускается через cron каждый день в 23:00
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from math import ceil

# Добавляем путь к проекту в PYTHONPATH
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

try:
    from database.schemas import schema
    import asyncpg
    import logging
    from config import settings
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    sys.exit(1)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/daily_attendance.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('daily_attendance')

async def execute_raw_sql(query: str, *params):
    """Функция выполнения SQL запросов"""
    try:
        conn = await asyncpg.connect(**settings.db.pg_link)
        try:
            if params:
                result = await conn.fetch(query, *params)
            else:
                result = await conn.fetch(query)
            return result
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        raise

async def calculate_next_payment_date(student_id: int, current_balance: int, days_per_week: int) -> datetime:
    """
    Рассчитывает следующую дату оплаты на основе:
    - текущего баланса занятий
    - количества тренировочных дней в неделю
    - текущей даты
    """
    try:
        today = datetime.now().date()
        
        # Получаем расписание студента для определения дней недели
        schedule_data = await execute_raw_sql(
            f"""SELECT DISTINCT sched.day_week 
            FROM {schema}.student_schedule ss
            JOIN {schema}.schedule sched ON ss.schedule = sched.id
            WHERE ss.student = $1""",
            student_id
        )
        
        if not schedule_data:
            logger.warning(f"⚠️ У студента ID {student_id} нет расписания")
            return today + timedelta(days=30)  # По умолчанию через 30 дней
        
        # Определяем дни недели студента
        student_days = [row['day_week'] for row in schedule_data]
        actual_days_per_week = len(student_days)
        
        # Если переданное количество дней не совпадает с фактическим, используем фактическое
        if days_per_week != actual_days_per_week:
            logger.info(f"📝 Корректировка дней в неделю для студента {student_id}: {days_per_week} -> {actual_days_per_week}")
            days_per_week = actual_days_per_week
        
        if days_per_week == 0:
            return today + timedelta(days=30)
        
        # Рассчитываем, на сколько недель хватит текущего баланса
        weeks_remaining = ceil(current_balance / days_per_week)
        
        # Находим ближайший тренировочный день для расчета даты
        weekdays_ru_to_int = {
            'понедельник': 0,
            'вторник': 1,
            'среда': 2,
            'четверг': 3,
            'пятница': 4,
            'суббота': 5,
            'воскресенье': 6
        }
        
        # Преобразуем русские названия дней в числовые
        student_weekdays = [weekdays_ru_to_int[day] for day in student_days]
        student_weekdays.sort()
        
        # Находим следующий тренировочный день после сегодняшнего
        today_weekday = today.weekday()
        next_training_day = None
        
        for day in student_weekdays:
            if day > today_weekday:
                next_training_day = day
                break
        
        # Если следующий тренировочный день на следующей неделе
        if next_training_day is None:
            next_training_day = student_weekdays[0]
            days_until_next = 7 - today_weekday + next_training_day
        else:
            days_until_next = next_training_day - today_weekday
        
        # Рассчитываем дату последнего занятия
        last_training_date = today + timedelta(days=days_until_next + (weeks_remaining - 1) * 7)
        
        # Добавляем буфер в 3 дня после последнего занятия для оплаты
        payment_date = last_training_date + timedelta(days=3)
        
        logger.debug(f"📅 Студент {student_id}: баланс {current_balance}, дней/неделю {days_per_week}, оплата {payment_date}")
        
        return payment_date
        
    except Exception as e:
        logger.error(f"❌ Ошибка расчета даты оплаты для студента {student_id}: {str(e)}")
        return datetime.now().date() + timedelta(days=30)

async def subtract_classes_and_update_payment_dates():
    """
    Ежедневная функция для:
    1. Вычитания занятий у студентов по расписанию
    2. Обновления дат следующей оплаты
    """
    try:
        # Получаем текущий день недели на русском
        weekdays_ru = {
            0: 'понедельник',
            1: 'вторник', 
            2: 'среда',
            3: 'четверг',
            4: 'пятница', 
            5: 'суббота',
            6: 'воскресенье'
        }
        
        today = datetime.now()
        today_weekday_ru = weekdays_ru[today.weekday()]
        today_date = today.date()
        
        logger.info(f"🚀 Запуск вычитания занятий за {today_date} ({today_weekday_ru})")
        
        # ШАГ 1: Вычитаем занятия у студентов
        result = await execute_raw_sql(
            f"""UPDATE {schema}.student 
            SET classes_remaining = classes_remaining - 1 
            WHERE id IN (
                SELECT DISTINCT ss.student
                FROM {schema}.student_schedule ss
                JOIN {schema}.schedule sched ON ss.schedule = sched.id
                JOIN {schema}.student s ON ss.student = s.id
                WHERE sched.day_week = $1
                AND s.active = true
                AND s.classes_remaining > 0
            )
            AND active = true
            AND classes_remaining > 0
            RETURNING id, name, classes_remaining;""",
            today_weekday_ru
        )
        
        updated_count = len(result)
        
        if updated_count == 0:
            logger.info(f"ℹ️ На {today_weekday_ru} не было студентов для списания")
            return {
                "success": True, 
                "message": "Нет студентов для списания", 
                "updated": 0,
                "payment_dates_updated": 0,
                "date": today_date.isoformat(),
                "weekday": today_weekday_ru
            }
        
        logger.info(f"✅ Списано занятий у {updated_count} студентов")
        
        # ШАГ 2: Обновляем даты оплаты для всех активных студентов
        payment_updates = 0
        all_active_students = await execute_raw_sql(
            f"""SELECT s.id, s.name, s.classes_remaining, COUNT(DISTINCT ss.schedule) as training_days_per_week
            FROM {schema}.student s
            LEFT JOIN {schema}.student_schedule ss ON s.id = ss.student
            WHERE s.active = true
            GROUP BY s.id, s.name, s.classes_remaining
            HAVING COUNT(DISTINCT ss.schedule) > 0"""
        )
        
        for student in all_active_students:
            try:
                next_payment_date = await calculate_next_payment_date(
                    student['id'], 
                    student['classes_remaining'],
                    student['training_days_per_week']
                )
                
                # Обновляем дату оплаты в базе
                await execute_raw_sql(
                    f"UPDATE {schema}.student SET expected_payment_date = $1 WHERE id = $2",
                    next_payment_date, student['id']
                )
                
                payment_updates += 1
                logger.debug(f"📅 Обновлена дата оплаты для {student['name']}: {next_payment_date}")
                
            except Exception as e:
                logger.error(f"❌ Ошибка обновления даты оплаты для {student['name']}: {str(e)}")
        
        logger.info(f"✅ Обновлено дат оплаты: {payment_updates} студентов")
        
        # Краткий отчет по списаниям
        logger.info("📊 Отчет по списаниям:")
        for student in result[:5]:
            logger.info(f"   👉 {student['name']} - осталось {student['classes_remaining']} занятий")
        if updated_count > 5:
            logger.info(f"   ... и еще {updated_count - 5} студентов")
        
        return {
            "success": True,
            "message": f"✅ Списано занятий у {updated_count} студентов, обновлено {payment_updates} дат оплаты",
            "updated": updated_count,
            "payment_dates_updated": payment_updates,
            "date": today_date.isoformat(),
            "weekday": today_weekday_ru
        }
        
    except Exception as e:
        error_msg = f"💥 Критическая ошибка: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "message": error_msg,
            "updated": 0,
            "payment_dates_updated": 0,
            "errors": [str(e)]
        }

async def main():
    """Основная функция для запуска через cron"""
    try:
        logger.info("=" * 50)
        logger.info("🏁 НАЧАЛО ВЫПОЛНЕНИЯ СКРИПТА")
        
        result = await subtract_classes_and_update_payment_dates()
        
        logger.info(f"🏁 РЕЗУЛЬТАТ: {result['message']}")
        logger.info("=" * 50)
        
        # Возвращаем код выхода для cron
        sys.exit(0 if result['success'] else 1)
        
    except Exception as e:
        logger.error(f"💥 Фатальная ошибка: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())