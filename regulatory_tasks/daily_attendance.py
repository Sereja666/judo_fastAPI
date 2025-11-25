#!/usr/bin/env python3
"""
Ежедневное вычитание занятий за посещения и расчет даты следующей оплаты
Запускается через cron каждый день в 23:00
"""

import asyncio
import sys
import os
import argparse
from datetime import datetime, timedelta
from math import ceil

# Добавляем путь к проекту в PYTHONPATH
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

try:
    from logger_config import logger
    from database.schemas import schema
    import asyncpg
    from config import settings
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    sys.exit(1)


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


async def calculate_next_payment_date(student_id: int, current_balance: int, days_per_week: int,
                                      target_date: datetime) -> datetime:
    """
    Рассчитывает следующую дату оплаты на основе:
    - текущего баланса занятий (может быть отрицательным)
    - количества тренировочных дней в неделю
    - целевой даты
    """
    try:
        today = target_date.date()

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
            logger.info(
                f"📝 Корректировка дней в неделю для студента {student_id}: {days_per_week} -> {actual_days_per_week}")
            days_per_week = actual_days_per_week

        if days_per_week == 0:
            return today + timedelta(days=30)

        # Рассчитываем, на сколько недель хватит текущего баланса (учитываем отрицательный баланс)
        if current_balance <= 0:
            # Если баланс отрицательный или нулевой, оплата нужна немедленно
            weeks_remaining = 0
        else:
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

        # Находим следующий тренировочный день после целевой даты
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

        if weeks_remaining <= 0:
            # Если баланс отрицательный или нулевой, оплата нужна немедленно
            payment_date = today + timedelta(days=3)  # +3 дня буфер
        else:
            # Рассчитываем дату последнего занятия
            last_training_date = today + timedelta(days=days_until_next + (weeks_remaining - 1) * 7)

            # Добавляем буфер в 3 дня после последнего занятия для оплаты
            payment_date = last_training_date + timedelta(days=3)

        logger.debug(
            f"📅 Студент {student_id}: баланс {current_balance}, дней/неделю {days_per_week}, оплата {payment_date}")

        return payment_date

    except Exception as e:
        logger.error(f"❌ Ошибка расчета даты оплаты для студента {student_id}: {str(e)}")
        return target_date.date() + timedelta(days=30)


async def process_8_classes_students(today_date, today_weekday_ru, is_saturday):
    """
    Обработка студентов с classes_in_price = 8
    - В понедельник-пятницу: списываем 1 занятие если был visit в этот день
    - В субботу: списываем по количеству visit + корректируем до 2 занятий в неделю
    """
    try:
        # Определяем начало и конец недели (понедельник - воскресенье)
        start_of_week = today_date - timedelta(days=today_date.weekday())  # Понедельник
        end_of_week = start_of_week + timedelta(days=6)  # Воскресенье

        # Получаем всех активных студентов с тарифом 8 занятий (исключаем NULL в classes_remaining)
        students_8 = await execute_raw_sql(
            f"""SELECT s.id, s.name, s.classes_remaining, s.price
            FROM {schema}.student s
            JOIN {schema}.price p ON s.price = p.id
            WHERE s.active = true
            AND p.classes_in_price = 8
            AND s.classes_remaining IS NOT NULL"""  # Исключаем NULL
        )

        if not students_8:
            logger.info("ℹ️ Нет студентов с тарифом 8 занятий (или у всех NULL в classes_remaining)")
            return []

        logger.info(f"🔍 Найдено {len(students_8)} студентов с тарифом 8 занятий")

        updated_students = []

        for student in students_8:
            try:
                # Дополнительная проверка на случай если в данных все равно попадется NULL
                if student['classes_remaining'] is None:
                    logger.warning(
                        f"⚠️ Студент {student['name']} (ID: {student['id']}) имеет NULL в classes_remaining - пропускаем")
                    continue

                if is_saturday:
                    # ЛОГИКА ДЛЯ СУББОТЫ

                    # 1. Сначала списываем посещения за субботу
                    saturday_visits = await execute_raw_sql(
                        f"""SELECT COUNT(*) as visit_count
                        FROM {schema}.visit v
                        WHERE v.student = $1 
                        AND DATE(v.data) = $2""",
                        student['id'], today_date
                    )

                    saturday_visit_count = saturday_visits[0]['visit_count'] if saturday_visits else 0

                    # Списываем посещения за субботу
                    if saturday_visit_count > 0:
                        await execute_raw_sql(
                            f"""UPDATE {schema}.student 
                            SET classes_remaining = classes_remaining - $1
                            WHERE id = $2""",
                            saturday_visit_count, student['id']
                        )
                        logger.info(
                            f"📅 Суббота: студент {student['name']} - списано {saturday_visit_count} занятий за посещения")

                    # 2. Проверяем посещения за всю неделю и корректируем до 2 занятий
                    weekly_visits = await execute_raw_sql(
                        f"""SELECT COUNT(*) as visit_count
                        FROM {schema}.visit v
                        WHERE v.student = $1 
                        AND DATE(v.data) >= $2 
                        AND DATE(v.data) <= $3""",
                        student['id'], start_of_week.date(), end_of_week.date()
                    )

                    weekly_visit_count = weekly_visits[0]['visit_count'] if weekly_visits else 0
                    expected_visits = 2  # Ожидаемое количество посещений в неделю для тарифа 8

                    logger.info(
                        f"📊 Студент {student['name']}: посещений за неделю {weekly_visit_count}, ожидается {expected_visits}")

                    # Определяем сколько нужно списать дополнительно
                    if weekly_visit_count < expected_visits:
                        # Если посещений меньше ожидаемых - списываем разницу
                        additional_classes_to_subtract = expected_visits - weekly_visit_count
                        logger.info(
                            f"📝 {student['name']}: недостаточно посещений, дополнительно списываем {additional_classes_to_subtract} занятий")

                        # Выполняем дополнительное списание
                        result = await execute_raw_sql(
                            f"""UPDATE {schema}.student 
                            SET classes_remaining = classes_remaining - $1
                            WHERE id = $2
                            RETURNING id, name, classes_remaining, price;""",
                            additional_classes_to_subtract, student['id']
                        )

                        if result:
                            updated_students.append(result[0])
                            total_subtracted = saturday_visit_count + additional_classes_to_subtract
                            logger.info(
                                f"✅ Студент {student['name']}: всего списано {total_subtracted} занятий, осталось {result[0]['classes_remaining']}")
                    else:
                        # Если посещений достаточно - только списываем субботние посещения
                        result = await execute_raw_sql(
                            f"""SELECT id, name, classes_remaining, price 
                            FROM {schema}.student 
                            WHERE id = $1""",
                            student['id']
                        )
                        if result:
                            updated_students.append(result[0])
                            logger.info(
                                f"✅ Студент {student['name']}: посещений достаточно, списано только {saturday_visit_count} за субботу, осталось {result[0]['classes_remaining']}")

                else:
                    # ЛОГИКА ДЛЯ ПОНЕДЕЛЬНИКА-ПЯТНИЦЫ
                    # Списываем 1 занятие если был visit в этот день
                    today_visits = await execute_raw_sql(
                        f"""SELECT COUNT(*) as visit_count
                        FROM {schema}.visit v
                        WHERE v.student = $1 
                        AND DATE(v.data) = $2""",
                        student['id'], today_date
                    )

                    today_visit_count = today_visits[0]['visit_count'] if today_visits else 0

                    if today_visit_count > 0:
                        # Был хотя бы один visit - списываем 1 занятие
                        result = await execute_raw_sql(
                            f"""UPDATE {schema}.student 
                            SET classes_remaining = classes_remaining - 1
                            WHERE id = $1
                            RETURNING id, name, classes_remaining, price;""",
                            student['id']
                        )

                        if result:
                            updated_students.append(result[0])
                            logger.info(
                                f"📅 {today_weekday_ru}: студент {student['name']} - списано 1 занятие за посещение, осталось {result[0]['classes_remaining']}")
                    else:
                        # Не было посещений - ничего не списываем
                        logger.info(
                            f"📅 {today_weekday_ru}: студент {student['name']} - не было посещений, списание не требуется")

            except Exception as e:
                logger.error(f"❌ Ошибка обработки студента {student['name']}: {str(e)}")

        return updated_students

    except Exception as e:
        logger.error(f"❌ Ошибка обработки студентов с тарифом 8: {str(e)}")
        return []


async def subtract_classes_and_update_payment_dates(target_date=None):
    """
    Ежедневная функция для списания занятий и обновления дат оплаты
    """
    try:
        # Если дата не указана, используем сегодняшнюю
        if target_date is None:
            target_date = datetime.now()
        elif isinstance(target_date, str):
            target_date = datetime.fromisoformat(target_date)

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

        today_weekday_ru = weekdays_ru[target_date.weekday()]
        today_date = target_date.date()
        is_saturday = target_date.weekday() == 5  # 5 = суббота

        logger.info(f"🚀 Запуск вычитания занятий за {today_date} ({today_weekday_ru})")

        # ОБРАБОТКА СТУДЕНТОВ С ТАРИФОМ 8 (отдельная логика)
        students_8_updated = await process_8_classes_students(today_date, today_weekday_ru, is_saturday)

        # ШАГ 1: Вычитаем занятия у остальных студентов (classes_in_price != 8)
        if is_saturday:
            # Для субботы: списываем количество занятий по факту посещений
            result = await execute_raw_sql(
                f"""UPDATE {schema}.student 
                SET classes_remaining = classes_remaining - 
                    CASE 
                        WHEN price IN (3, 4) THEN 2
                        ELSE GREATEST(1, (
                            SELECT COUNT(*) 
                            FROM {schema}.visit v
                            WHERE v.student = {schema}.student.id 
                            AND DATE(v.data) = $1
                            AND v.shedule IN (
                                SELECT ss.schedule 
                                FROM {schema}.student_schedule ss 
                                WHERE ss.student = {schema}.student.id
                            )
                        ))
                    END
                WHERE id IN (
                    SELECT DISTINCT ss.student
                    FROM {schema}.student_schedule ss
                    JOIN {schema}.schedule sched ON ss.schedule = sched.id
                    JOIN {schema}.student s ON ss.student = s.id
                    JOIN {schema}.price p ON s.price = p.id
                    WHERE sched.day_week = $2
                    AND s.active = true
                    AND p.classes_in_price != 8
                    AND s.classes_remaining IS NOT NULL 
                )
                AND active = true
                AND classes_remaining IS NOT NULL
                RETURNING id, name, classes_remaining, price;""",
                today_date, today_weekday_ru
            )
        else:
            # Для остальных дней: стандартное списание 1 занятия (максимум)
            result = await execute_raw_sql(
                f"""UPDATE {schema}.student 
                SET classes_remaining = classes_remaining - 1 
                WHERE id IN (
                    SELECT DISTINCT ss.student
                    FROM {schema}.student_schedule ss
                    JOIN {schema}.schedule sched ON ss.schedule = sched.id
                    JOIN {schema}.student s ON ss.student = s.id
                    JOIN {schema}.price p ON s.price = p.id
                    WHERE sched.day_week = $1
                    AND s.active = true
                    AND p.classes_in_price != 8
                    AND s.classes_remaining IS NOT NULL  
                )
                AND active = true
                AND classes_remaining IS NOT NULL 
                RETURNING id, name, classes_remaining, price;""",
                today_weekday_ru
            )

        # Объединяем результаты обычных студентов и студентов с тарифом 8
        all_updated_students = list(result) + students_8_updated
        updated_count = len(all_updated_students)

        if updated_count == 0:
            logger.info(
                f"ℹ️ На {today_weekday_ru} не было студентов для списания (или у всех NULL в classes_remaining)")
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
        multiple_visits_count = 0
        negative_balance_count = 0
        tariff_8_count = len(students_8_updated)

        for student in all_updated_students:
            # Проверяем ушел ли баланс в минус
            if student['classes_remaining'] < 0:
                negative_balance_count += 1
                logger.warning(f"⚠️ Студент {student['name']} ушел в минус: {student['classes_remaining']} занятий")

            # Проверяем тип тарифа для анализа (только для обычных студентов)
            if student not in students_8_updated:
                if is_saturday:
                    if student['price'] in [3, 4]:
                        special_tariff_count += 1
                    else:
                        # Для обычных тарифов в субботу проверяем количество посещений
                        visit_count = await execute_raw_sql(
                            f"""SELECT COUNT(*) as count
                            FROM {schema}.visit v
                            WHERE v.student = $1 
                            AND DATE(v.data) = $2
                            AND v.shedule IN (
                                SELECT ss.schedule 
                                FROM {schema}.student_schedule ss 
                                WHERE ss.student = $1
                            )""",
                            student['id'], today_date
                        )

                        visit_count = visit_count[0]['count'] if visit_count else 0
                        if visit_count > 1:
                            multiple_visits_count += 1
                        else:
                            regular_count += 1
                else:
                    regular_count += 1

        logger.info(f"✅ Списано занятий у {updated_count} студентов")

        if is_saturday:
            logger.info(
                f"🎯 По субботам: {special_tariff_count} студентов списано по 2 занятия (особый тариф), "
                f"{multiple_visits_count} студентов списано по количеству посещений, "
                f"{regular_count} студентов по 1 занятию, "
                f"{tariff_8_count} студентов с тарифом 8 обработано")

        if negative_balance_count > 0:
            logger.warning(f"🔴 {negative_balance_count} студентов ушли в отрицательный баланс!")

        # ШАГ 2: Обновляем даты оплаты для всех активных студентов (только с не-NULL балансом)
        payment_updates = 0
        all_active_students = await execute_raw_sql(
            f"""SELECT s.id, s.name, s.classes_remaining, s.price,
                    COUNT(DISTINCT ss.schedule) as training_days_per_week
            FROM {schema}.student s
            LEFT JOIN {schema}.student_schedule ss ON s.id = ss.student
            JOIN {schema}.price p ON s.price = p.id
            WHERE s.active = true
            AND s.classes_remaining IS NOT NULL 
            GROUP BY s.id, s.name, s.classes_remaining, s.price
            HAVING COUNT(DISTINCT ss.schedule) > 0"""
        )

        # Добавляем счетчик для студентов с NULL балансом
        null_balance_count = 0
        null_students = await execute_raw_sql(
            f"""SELECT COUNT(*) as count
            FROM {schema}.student 
            WHERE active = true 
            AND classes_remaining IS NULL"""
        )

        if null_students and null_students[0]['count'] > 0:
            null_balance_count = null_students[0]['count']
            logger.warning(f"⚠️ Обнаружено {null_balance_count} студентов с NULL в classes_remaining - они пропущены")

        for student in all_active_students:
            try:
                # Учитываем особые тарифы при расчете дней в неделю
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
                        actual_days_per_week += 1

                next_payment_date = await calculate_next_payment_date(
                    student['id'],
                    student['classes_remaining'],
                    actual_days_per_week,
                    target_date
                )

                # Обновляем дату оплаты в базе
                await execute_raw_sql(
                    f"UPDATE {schema}.student SET expected_payment_date = $1 WHERE id = $2",
                    next_payment_date, student['id']
                )

                payment_updates += 1
                logger.info(
                    f"📅 Обновлена дата оплаты для {student['name']}: {next_payment_date} (баланс: {student['classes_remaining']})")

            except Exception as e:
                logger.error(f"❌ Ошибка обновления даты оплаты для {student['name']}: {str(e)}")

        logger.info(f"✅ Обновлено дат оплаты: {payment_updates} студентов")

        # Краткий отчет по списаниям
        logger.info("📊 Отчет по списаниям:")
        for student in all_updated_students[:5]:
            balance_status = "🔴 МИНУС" if student['classes_remaining'] < 0 else "🟢"

            if student in students_8_updated:
                logger.info(
                    f"   👉 {student['name']} - тариф 8, осталось {student['classes_remaining']} {balance_status}")
            elif is_saturday and student['price'] in [3, 4]:
                logger.info(
                    f"   👉 {student['name']} - списано 2 занятия, осталось {student['classes_remaining']} {balance_status} (особый тариф)")
            elif is_saturday:
                # Для обычных тарифов в субботу показываем количество посещений
                visit_count = await execute_raw_sql(
                    f"""SELECT COUNT(*) as count
                    FROM {schema}.visit v
                    WHERE v.student = $1 
                    AND DATE(v.data) = $2
                    AND v.shedule IN (
                        SELECT ss.schedule 
                        FROM {schema}.student_schedule ss 
                        WHERE ss.student = $1
                    )""",
                    student['id'], today_date
                )
                visit_count = visit_count[0]['count'] if visit_count else 1
                logger.info(
                    f"   👉 {student['name']} - списано {visit_count} занятий, осталось {student['classes_remaining']} {balance_status}")
            else:
                logger.info(
                    f"   👉 {student['name']} - списано 1 занятие, осталось {student['classes_remaining']} {balance_status}")

        if updated_count > 5:
            logger.info(f"   ... и еще {updated_count - 5} студентов")

        # Дополняем сообщение информацией о пропущенных студентах
        message_suffix = ""
        if null_balance_count > 0:
            message_suffix = f", пропущено {null_balance_count} студентов с NULL балансом"

        return {
            "success": True,
            "message": f"✅ Списано занятий у {updated_count} студентов, обновлено {payment_updates} дат оплаты{message_suffix}",
            "updated": updated_count,
            "special_tariff_count": special_tariff_count if is_saturday else 0,
            "multiple_visits_count": multiple_visits_count if is_saturday else 0,
            "tariff_8_count": tariff_8_count,
            "negative_balance_count": negative_balance_count,
            "null_balance_skipped": null_balance_count,
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
        # Парсинг аргументов командной строки
        parser = argparse.ArgumentParser(description='Ежедневное списание занятий')
        parser.add_argument('--date', type=str, help='Дата для обработки в формате YYYY-MM-DD (по умолчанию сегодня)')
        args = parser.parse_args()

        # Определяем целевую дату
        if args.date:
            target_date = datetime.fromisoformat(args.date)
            logger.info(f"🎯 Обработка для указанной даты: {target_date.date()}")
        else:
            target_date = datetime.now()
            logger.info(f"🎯 Обработка для сегодняшней даты: {target_date.date()}")

        logger.info("=" * 50)
        logger.info("🏁 НАЧАЛО ВЫПОЛНЕНИЯ СКРИПТА")

        result = await subtract_classes_and_update_payment_dates(target_date)

        logger.info(f"🏁 РЕЗУЛЬТАТ: {result['message']}")
        logger.info("=" * 50)

        # Возвращаем код выхода для cron
        sys.exit(0 if result['success'] else 1)

    except Exception as e:
        logger.error(f"💥 Фатальная ошибка: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())