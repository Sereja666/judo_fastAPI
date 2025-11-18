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
from logger_config import logger

# Добавляем путь к проекту в PYTHONPATH
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

try:
    from database.schemas import schema
    import asyncpg
    import logging
    from config import settings
except ImportError as e:
    logger.error(f"❌ Ошибка импорта: {e}")
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
    2. Учитывает особые тарифы (2 занятия по субботам для price_id = 3 или 4)
    3. Обновления дат следующей оплаты
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
        is_saturday = today.weekday() == 5  # 5 = суббота

        logger.info(f"🚀 Запуск вычитания занятий за {today_date} ({today_weekday_ru})")

        # ШАГ 1: Вычитаем занятия у студентов с учетом особых тарифов
        if is_saturday:
            # Для субботы: особые условия для price_id = 3 или 4
            result = await execute_raw_sql(
                f"""UPDATE {schema}.student 
                SET classes_remaining = classes_remaining - 
                    CASE 
                        WHEN price IN (3, 4) THEN 2
                        ELSE 1
                    END
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
                RETURNING id, name, classes_remaining, price;""",
                today_weekday_ru
            )
        else:
            # Для остальных дней: стандартное списание 1 занятия
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
                RETURNING id, name, classes_remaining, price;""",
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

        # Анализируем результаты списания
        special_tariff_count = 0
        regular_count = 0

        for student in result:
            if is_saturday and student['price'] in [3, 4]:
                special_tariff_count += 1
            else:
                regular_count += 1

        logger.info(f"✅ Списано занятий у {updated_count} студентов")

        if is_saturday:
            logger.info(
                f"🎯 По субботам: {special_tariff_count} студентов списано по 2 занятия, {regular_count} студентов по 1 занятию")

        # ШАГ 2: Обновляем даты оплаты для всех активных студентов
        payment_updates = 0
        all_active_students = await execute_raw_sql(
            f"""SELECT s.id, s.name, s.classes_remaining, s.price,
                    COUNT(DISTINCT ss.schedule) as training_days_per_week
            FROM {schema}.student s
            LEFT JOIN {schema}.student_schedule ss ON s.id = ss.student
            WHERE s.active = true
            GROUP BY s.id, s.name, s.classes_remaining, s.price
            HAVING COUNT(DISTINCT ss.schedule) > 0"""
        )

        for student in all_active_students:
            try:
                # Учитываем особые тарифы при расчете дней в неделю
                # Для price_id = 3 или 4 в субботу считаем как 2 дня
                actual_days_per_week = student['training_days_per_week']

                if student['price'] in [3, 4]:
                    # Проверяем, есть ли у студента тренировки в субботу
                    saturday_schedule = await execute_raw_sql(
                        f"""SELECT 1 
                        FROM {schema}.student_schedule ss
                        JOIN {schema}.schedule sched ON ss.schedule = sched.id
                        WHERE ss.student = $1 AND sched.day_week = 'суббота'
                        LIMIT 1;""",
                        student['id']
                    )
                    if saturday_schedule:
                        # Увеличиваем эффективное количество дней для расчета
                        actual_days_per_week += 1

                next_payment_date = await calculate_next_payment_date(
                    student['id'],
                    student['classes_remaining'],
                    actual_days_per_week
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
            if is_saturday and student['price'] in [3, 4]:
                logger.info(
                    f"   👉 {student['name']} - списано 2 занятия, осталось {student['classes_remaining']} (особый тариф)")
            else:
                logger.info(f"   👉 {student['name']} - списано 1 занятие, осталось {student['classes_remaining']}")

        if updated_count > 5:
            logger.info(f"   ... и еще {updated_count - 5} студентов")

        return {
            "success": True,
            "message": f"✅ Списано занятий у {updated_count} студентов, обновлено {payment_updates} дат оплаты" +
                       (f", из них {special_tariff_count} по 2 занятия" if is_saturday else ""),
            "updated": updated_count,
            "special_tariff_count": special_tariff_count if is_saturday else 0,
            "regular_count": regular_count,
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