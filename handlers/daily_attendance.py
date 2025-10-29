#!/usr/bin/env python3
"""
Ежедневное вычитание занятий за посещения
Запускается через cron каждый день в 23:00

## Открыть crontab для редактирования
crontab -e

# Добавить строку (запуск каждый день в 23:00)
0 23 * * * /usr/bin/python3 /path/to/your/project/daily_attendance.py

# Или с логированием в отдельный файл
0 23 * * * /usr/bin/python3 /path/to/your/project/daily_attendance.py >> /var/log/daily_attendance_cron.log 2>&1
chmod +x /path/to/your/project/daily_attendance.py
Прямой запуск
python3 /path/to/your/project/daily_attendance.py

# Или через cron вручную (если настроен)
/path/to/your/project/daily_attendance.py
Просмотр логов
tail -f /var/log/daily_attendance.log

# Проверка cron логов
grep CRON /var/log/syslog

# Проверка выполнения
grep "ОБНОВЛЕНО" /var/log/daily_attendance.log
"""

import asyncio
import sys
import os
from datetime import datetime, date

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db_handler.db_funk import execute_raw_sql
from database.schemas import schema
import logging

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


async def subtract_classes_for_todays_attendance():
    """
    Ежедневная функция для вычитания занятий у студентов, которые должны были прийти сегодня.
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

        # 1. Находим расписания на сегодняшний день недели
        schedules = await execute_raw_sql(
            f"SELECT id, day_week, time_start, time_end FROM {schema}.schedule WHERE day_week = $1;",
            today_weekday_ru
        )

        if not schedules:
            logger.info(f"ℹ️ На {today_weekday_ru} нет расписаний")
            return {"success": True, "message": "Нет расписаний на сегодня", "updated": 0}

        schedule_ids = [s['id'] for s in schedules]
        logger.info(f"📅 Найдено расписаний: {len(schedule_ids)}")

        # 2. Находим студентов, привязанных к этим расписаниям
        student_schedules = await execute_raw_sql(
            f"""SELECT ss.student, ss.schedule, s.name, s.classes_remaining
            FROM {schema}.student_schedule ss
            JOIN {schema}.student s ON ss.student = s.id
            WHERE ss.schedule = ANY($1::int[]) 
            AND s.active = true
            AND s.classes_remaining > 0;""",
            schedule_ids
        )

        if not student_schedules:
            logger.info("ℹ️ Нет активных студентов с занятиями на сегодня")
            return {"success": True, "message": "Нет студентов для обновления", "updated": 0}

        student_ids = list(set([ss['student'] for ss in student_schedules]))
        logger.info(f"👥 Найдено студентов для обновления: {len(student_ids)}")

        # 3. Вычитаем по 1 занятию у каждого студента
        updated_count = 0
        errors = []
        updated_students = []

        for student_schedule in student_schedules:
            student_id = student_schedule['student']
            try:
                result = await execute_raw_sql(
                    f"""UPDATE {schema}.student 
                    SET classes_remaining = classes_remaining - 1 
                    WHERE id = $1 
                    AND active = true 
                    AND classes_remaining > 0
                    RETURNING id, name, classes_remaining;""",
                    student_id
                )

                if result:
                    updated_count += 1
                    student = result[0]
                    updated_students.append({
                        'id': student['id'],
                        'name': student['name'],
                        'remaining': student['classes_remaining']
                    })
                    logger.info(
                        f"✅ Обновлен: {student['name']} (ID: {student['id']}) - осталось: {student['classes_remaining']}")
                else:
                    errors.append(f"Студент {student_id}: не удалось обновить (возможно, 0 занятий)")
                    logger.warning(f"⚠️ Не обновлен студент {student_id}: 0 занятий")

            except Exception as e:
                errors.append(f"Студент {student_id}: {str(e)}")
                logger.error(f"❌ Ошибка студента {student_id}: {str(e)}")

        # 4. Логируем итог
        message = f"✅ Обновлено: {updated_count}/{len(student_ids)} студентов"
        if errors:
            message += f", ❌ ошибок: {len(errors)}"

        logger.info(f"🎯 Завершено: {message}")

        # Детальный отчет
        if updated_students:
            logger.info("📊 Детальный отчет:")
            for student in updated_students:
                logger.info(f"   👉 {student['name']} (ID: {student['id']}) - осталось {student['remaining']} занятий")

        return {
            "success": True,
            "message": message,
            "updated": updated_count,
            "total_students": len(student_ids),
            "errors": errors,
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
            "errors": [str(e)]
        }


async def main():
    """Основная функция для запуска через cron"""
    try:
        logger.info("=" * 50)
        logger.info("🏁 НАЧАЛО ВЫПОЛНЕНИЯ СКРИПТА")

        result = await subtract_classes_for_todays_attendance()

        logger.info(f"🏁 РЕЗУЛЬТАТ: {result['message']}")
        logger.info("=" * 50)

        # Возвращаем код выхода для cron
        sys.exit(0 if result['success'] else 1)

    except Exception as e:
        logger.error(f"💥 Фатальная ошибка: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())


