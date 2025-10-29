#!/usr/bin/env python3
"""
Ежедневное вычитание занятий за посещения
Запускается через cron каждый день в 23:00
Компактная версия - 1 SQL запрос
"""

import asyncio
import sys
import os
from datetime import datetime

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

async def subtract_classes_for_todays_attendance():
    """
    Ежедневная функция для вычитания занятий у студентов по расписанию
    Один SQL запрос для максимальной эффективности
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
        
        # ОДИН SQL ЗАПРОС ДЛЯ ВСЕГО!
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
                "date": today_date.isoformat(),
                "weekday": today_weekday_ru
            }
        
        logger.info(f"✅ Списано занятий у {updated_count} студентов")
        
        # Краткий отчет (первые 5 студентов)
        logger.info("📊 Отчет по списаниям:")
        for student in result[:5]:
            logger.info(f"   👉 {student['name']} - осталось {student['classes_remaining']} занятий")
        if updated_count > 5:
            logger.info(f"   ... и еще {updated_count - 5} студентов")
        
        return {
            "success": True,
            "message": f"✅ Списано занятий у {updated_count} студентов",
            "updated": updated_count,
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