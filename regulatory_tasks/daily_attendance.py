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
from typing import Dict, List, Optional, Any

# Добавляем путь к проекту в PYTHONPATH
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

try:
    from logger_config import logger
    from database.models import schema, Lesson_write_offs
    import asyncpg
    from config import settings
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    sys.exit(1)


class AttendanceProcessor:
    """Класс для обработки посещений и списаний занятий"""

    # Константы
    WEEKDAYS_RU = {
        0: 'понедельник',
        1: 'вторник',
        2: 'среда',
        3: 'четверг',
        4: 'пятница',
        5: 'суббота',
        6: 'воскресенье'
    }

    WEEKDAYS_RU_TO_INT = {
        'понедельник': 0,
        'вторник': 1,
        'среда': 2,
        'четверг': 3,
        'пятница': 4,
        'суббота': 5,
        'воскресенье': 6
    }

    SPECIAL_TARIFFS = [3, 4]  # Особые тарифы (списание по 2 занятия в субботу)

    def __init__(self):
        self.schema = schema

    async def execute_raw_sql(self, query: str, *params) -> List[Any]:
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

    async def execute_write(self, query: str, *params):
        """Функция выполнения SQL запросов на запись"""
        try:
            conn = await asyncpg.connect(**settings.db.pg_link)
            try:
                await conn.execute(query, *params)
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Database write error: {str(e)}")
            raise

    async def record_write_off(self, student_id: int, quantity: int, write_off_date: datetime):
        """Запись факта списания в таблицу lesson_write_offs"""
        try:
            await self.execute_write(
                f"""INSERT INTO {self.schema}.lesson_write_offs 
                (data, student_id, quantity) 
                VALUES ($1, $2, $3)""",
                write_off_date, student_id, quantity
            )
            logger.debug(f"📝 Записано списание: студент {student_id}, кол-во {quantity}, дата {write_off_date}")
        except Exception as e:
            logger.error(f"❌ Ошибка записи списания для студента {student_id}: {str(e)}")

    async def get_student_schedule_days(self, student_id: int) -> List[str]:
        """Получить дни расписания студента"""
        schedule_data = await self.execute_raw_sql(
            f"""SELECT DISTINCT sched.day_week 
            FROM {self.schema}.student_schedule ss
            JOIN {self.schema}.schedule sched ON ss.schedule = sched.id
            WHERE ss.student = $1""",
            student_id
        )
        return [row['day_week'] for row in schedule_data] if schedule_data else []

    async def calculate_next_payment_date(self, student_id: int, current_balance: int,
                                          days_per_week: int, target_date: datetime) -> datetime:
        """
        Рассчитывает следующую дату оплаты
        """
        try:
            today = target_date.date()

            # Если баланс отрицательный (долг) - даем 3 дня на оплату
            if current_balance < 0:
                payment_date = today + timedelta(days=3)
                logger.info(f"💰 Студент ID {student_id} имеет долг {current_balance}, оплата до {payment_date}")
                return payment_date

            student_days = await self.get_student_schedule_days(student_id)

            if not student_days:
                logger.warning(f"⚠️ У студента ID {student_id} нет расписания")
                return today + timedelta(days=30)

            actual_days_per_week = len(student_days)
            if days_per_week != actual_days_per_week:
                logger.info(
                    f"📝 Корректировка дней для студента {student_id}: {days_per_week} -> {actual_days_per_week}")
                days_per_week = actual_days_per_week

            if days_per_week == 0:
                return today + timedelta(days=30)

            # Расчет оставшихся недель
            weeks_remaining = 0 if current_balance <= 0 else ceil(current_balance / days_per_week)

            # Преобразуем русские названия дней в числовые
            student_weekdays = [self.WEEKDAYS_RU_TO_INT[day] for day in student_days]
            student_weekdays.sort()

            # Находим следующий тренировочный день
            today_weekday = today.weekday()
            next_training_day = None

            for day in student_weekdays:
                if day > today_weekday:
                    next_training_day = day
                    break

            if next_training_day is None:
                next_training_day = student_weekdays[0]
                days_until_next = 7 - today_weekday + next_training_day
            else:
                days_until_next = next_training_day - today_weekday

            if weeks_remaining <= 0:
                payment_date = today + timedelta(days=3)  # +3 дня буфер
            else:
                last_training_date = today + timedelta(days=days_until_next + (weeks_remaining - 1) * 7)
                payment_date = last_training_date + timedelta(days=3)

            logger.debug(
                f"📅 Студент {student_id}: баланс {current_balance}, дней/неделю {days_per_week}, оплата {payment_date}")
            return payment_date

        except Exception as e:
            logger.error(f"❌ Ошибка расчета даты оплаты для студента {student_id}: {str(e)}")
            return target_date.date() + timedelta(days=30)

    async def get_visits_count(self, student_id: int, date_from: datetime, date_to: datetime = None) -> int:
        """Получить количество посещений студента за период"""
        if date_to is None:
            date_to = date_from

        visits = await self.execute_raw_sql(
            f"""SELECT COUNT(*) as visit_count
            FROM {self.schema}.visit v
            WHERE v.student = $1 
            AND DATE(v.data) >= $2 
            AND DATE(v.data) <= $3""",
            student_id, date_from.date(), date_to.date()
        )
        return visits[0]['visit_count'] if visits else 0

    async def has_schedule_or_visit(self, student_id: int, weekday_ru: str, target_date: datetime) -> bool:
        """Проверить, есть ли у студента расписание или посещение на указанный день"""
        result = await self.execute_raw_sql(
            f"""SELECT 1
            FROM {self.schema}.student_schedule ss
            JOIN {self.schema}.schedule sched ON ss.schedule = sched.id
            WHERE ss.student = $1 AND sched.day_week = $2

            UNION

            SELECT 1
            FROM {self.schema}.visit v
            WHERE v.student = $1 AND DATE(v.data) = $3
            LIMIT 1""",
            student_id, weekday_ru, target_date.date()
        )
        return len(result) > 0

    async def process_tariff_8_student(self, student: Dict, today_date: datetime,
                                       today_weekday_ru: str, is_saturday: bool) -> Optional[Dict]:
        """Обработка одного студента с тарифом 8 занятий"""
        try:
            if student['classes_remaining'] is None:
                logger.warning(f"⚠️ Студент {student['name']} имеет NULL в classes_remaining - пропускаем")
                return None

            if is_saturday:
                return await self._process_tariff_8_saturday(student, today_date)
            else:
                return await self._process_tariff_8_weekday(student, today_date, today_weekday_ru)

        except Exception as e:
            logger.error(f"❌ Ошибка обработки студента {student['name']}: {str(e)}")
            return None

    async def _process_tariff_8_saturday(self, student: Dict, today_date: datetime) -> Optional[Dict]:
        """Обработка студента с тарифом 8 в субботу"""
        # Проверяем, есть ли расписание или посещение в субботу
        has_schedule_or_visit = await self.has_schedule_or_visit(student['id'], 'суббота', today_date)

        if not has_schedule_or_visit:
            logger.info(f"📅 Суббота: студент {student['name']} - нет расписания и посещений")
            return None

        # 1. Списываем посещения за субботу
        saturday_visit_count = await self.get_visits_count(student['id'], today_date)

        if saturday_visit_count > 0:
            await self.execute_write(
                f"""UPDATE {self.schema}.student 
                SET classes_remaining = classes_remaining - $1
                WHERE id = $2""",
                saturday_visit_count, student['id']
            )
            # Записываем списание
            await self.record_write_off(student['id'], saturday_visit_count, today_date)
            logger.info(f"📅 Суббота: студент {student['name']} - списано {saturday_visit_count} занятий")

        # 2. Проверяем посещения за неделю и корректируем до 2 занятий
        start_of_week = today_date - timedelta(days=today_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        weekly_visit_count = await self.get_visits_count(student['id'], start_of_week, end_of_week)
        expected_visits = 2

        logger.info(
            f"📊 Студент {student['name']}: посещений за неделю {weekly_visit_count}, ожидается {expected_visits}")

        if weekly_visit_count < expected_visits:
            additional_classes_to_subtract = expected_visits - weekly_visit_count
            logger.info(f"📝 {student['name']}: дополнительно списываем {additional_classes_to_subtract} занятий")

            result = await self.execute_raw_sql(
                f"""UPDATE {self.schema}.student 
                SET classes_remaining = classes_remaining - $1
                WHERE id = $2
                RETURNING id, name, classes_remaining, price;""",
                additional_classes_to_subtract, student['id']
            )

            if result:
                # Записываем дополнительное списание
                await self.record_write_off(student['id'], additional_classes_to_subtract, today_date)

                total_subtracted = saturday_visit_count + additional_classes_to_subtract
                logger.info(f"✅ Студент {student['name']}: всего списано {total_subtracted} занятий")
                return result[0]
        else:
            result = await self.execute_raw_sql(
                f"""SELECT id, name, classes_remaining, price 
                FROM {self.schema}.student 
                WHERE id = $1""",
                student['id']
            )
            if result:
                logger.info(f"✅ Студент {student['name']}: посещений достаточно")
                return result[0]

        return None

    async def _process_tariff_8_weekday(self, student: Dict, today_date: datetime, today_weekday_ru: str) -> Optional[
        Dict]:
        """Обработка студента с тарифом 8 в будний день"""
        # Проверяем: есть ли расписание на сегодня ИЛИ было ли посещение
        has_schedule_or_visit = await self.has_schedule_or_visit(student['id'], today_weekday_ru, today_date)

        # Если нет ни расписания, ни посещения - не списываем
        if not has_schedule_or_visit:
            logger.info(f"📅 {today_weekday_ru}: студент {student['name']} - нет расписания и посещений")
            return None

        # Если есть расписание или посещение - списываем 1 занятие
        result = await self.execute_raw_sql(
            f"""UPDATE {self.schema}.student 
            SET classes_remaining = classes_remaining - 1
            WHERE id = $1
            RETURNING id, name, classes_remaining, price;""",
            student['id']
        )

        if result:
            # Записываем списание
            await self.record_write_off(student['id'], 1, today_date)
            logger.info(
                f"📅 {today_weekday_ru}: студент {student['name']} - списано 1 занятие (по расписанию или посещению)")
            return result[0]

        return None

    async def process_regular_students(self, today_date: datetime, today_weekday_ru: str, is_saturday: bool) -> List[
        Dict]:
        """Обработка обычных студентов (не тариф 8)"""
        if is_saturday:
            query = f"""UPDATE {self.schema}.student 
                SET classes_remaining = classes_remaining - 
                    CASE 
                        WHEN price IN ({','.join(map(str, self.SPECIAL_TARIFFS))}) THEN 2
                        ELSE GREATEST(1, (
                            SELECT COUNT(*) 
                            FROM {self.schema}.visit v
                            WHERE v.student = {self.schema}.student.id 
                            AND DATE(v.data) = $1
                        ))
                    END
                WHERE id IN (
                    -- Студенты, у которых есть либо расписание на субботу, либо посещение в субботу
                    SELECT DISTINCT s.id
                    FROM {self.schema}.student s
                    LEFT JOIN {self.schema}.student_schedule ss ON s.id = ss.student
                    LEFT JOIN {self.schema}.schedule sch ON ss.schedule = sch.id
                    LEFT JOIN {self.schema}.visit v ON s.id = v.student AND DATE(v.data) = $1
                    WHERE s.active = true
                    AND s.classes_remaining IS NOT NULL
                    AND (
                        sch.day_week = 'суббота'  -- Есть расписание на субботу
                        OR 
                        v.id IS NOT NULL  -- Или было посещение в субботу
                    )
                )
                AND active = true
                AND classes_remaining IS NOT NULL
                RETURNING id, name, classes_remaining, price;"""
            params = (today_date,)
        else:
            # Для будних дней
            query = f"""UPDATE {self.schema}.student 
                SET classes_remaining = classes_remaining - 1 
                WHERE id IN (
                    -- Студенты, у которых есть либо расписание на сегодня, либо посещение сегодня
                    SELECT DISTINCT s.id
                    FROM {self.schema}.student s
                    LEFT JOIN {self.schema}.student_schedule ss ON s.id = ss.student
                    LEFT JOIN {self.schema}.schedule sch ON ss.schedule = sch.id
                    LEFT JOIN {self.schema}.visit v ON s.id = v.student AND DATE(v.data) = $1
                    JOIN {self.schema}.price p ON s.price = p.id
                    WHERE s.active = true
                    AND p.classes_in_price != 8  -- Не тариф 8
                    AND s.classes_remaining IS NOT NULL
                    AND (
                        sch.day_week = $2  -- Есть расписание на сегодня
                        OR 
                        v.id IS NOT NULL   -- Или было посещение сегодня
                    )
                )
                RETURNING id, name, classes_remaining, price;"""
            params = (today_date, today_weekday_ru)

        result = await self.execute_raw_sql(query, *params)

        # Записываем списания в таблицу lesson_write_offs
        for student in result:
            quantity = 2 if (is_saturday and student['price'] in self.SPECIAL_TARIFFS) else 1
            await self.record_write_off(student['id'], quantity, today_date)

        return list(result)

    async def update_payment_dates(self, target_date: datetime) -> int:
        """Обновление дат оплаты для всех активных студентов"""
        all_active_students = await self.execute_raw_sql(
            f"""SELECT s.id, s.name, s.classes_remaining, s.price,
                    COUNT(DISTINCT ss.schedule) as training_days_per_week
            FROM {self.schema}.student s
            LEFT JOIN {self.schema}.student_schedule ss ON s.id = ss.student
            JOIN {self.schema}.price p ON s.price = p.id
            WHERE s.active = true
            AND s.classes_remaining IS NOT NULL
            GROUP BY s.id, s.name, s.classes_remaining, s.price
            HAVING COUNT(DISTINCT ss.schedule) > 0"""
        )

        payment_updates = 0
        for student in all_active_students:
            try:
                actual_days_per_week = student['training_days_per_week']

                # Учитываем особые тарифы
                if student['price'] in self.SPECIAL_TARIFFS:
                    saturday_schedule = await self.execute_raw_sql(
                        f"""SELECT 1 
                        FROM {self.schema}.student_schedule ss
                        JOIN {self.schema}.schedule sched ON ss.schedule = sched.id
                        WHERE ss.student = $1 AND sched.day_week = 'суббота'
                        LIMIT 1;""",
                        student['id']
                    )
                    if saturday_schedule:
                        actual_days_per_week += 1

                next_payment_date = await self.calculate_next_payment_date(
                    student['id'], student['classes_remaining'], actual_days_per_week, target_date
                )

                await self.execute_write(
                    f"UPDATE {self.schema}.student SET expected_payment_date = $1 WHERE id = $2",
                    next_payment_date, student['id']
                )

                payment_updates += 1
                logger.info(f"📅 Обновлена дата оплаты для {student['name']}: {next_payment_date}")

            except Exception as e:
                logger.error(f"❌ Ошибка обновления даты оплаты для {student['name']}: {str(e)}")

        return payment_updates

    async def subtract_classes_and_update_payment_dates(self, target_date: datetime = None) -> Dict[str, Any]:
        """
        Основная функция для списания занятий и обновления дат оплаты
        """
        try:
            if target_date is None:
                target_date = datetime.now()
            elif isinstance(target_date, str):
                target_date = datetime.fromisoformat(target_date)

            today_weekday_ru = self.WEEKDAYS_RU[target_date.weekday()]
            today_date = target_date.date()
            is_saturday = target_date.weekday() == 5

            logger.info(f"🚀 Запуск вычитания занятий за {today_date} ({today_weekday_ru})")

            # 1. Обработка студентов с тарифом 8
            tariff_8_students = await self.execute_raw_sql(
                f"""SELECT s.id, s.name, s.classes_remaining, s.price
                FROM {self.schema}.student s
                JOIN {self.schema}.price p ON s.price = p.id
                WHERE s.active = true
                AND p.classes_in_price = 8
                AND s.classes_remaining IS NOT NULL"""
            )

            students_8_updated = []
            for student in tariff_8_students:
                result = await self.process_tariff_8_student(student, target_date, today_weekday_ru, is_saturday)
                if result:
                    students_8_updated.append(result)

            # 2. Обработка обычных студентов
            regular_students_updated = await self.process_regular_students(target_date, today_weekday_ru, is_saturday)

            # 3. Объединение результатов
            all_updated_students = regular_students_updated + students_8_updated
            updated_count = len(all_updated_students)

            if updated_count == 0:
                logger.info(f"ℹ️ На {today_weekday_ru} не было студентов для списания")
                return self._create_response(True, "Нет студентов для списания", 0, 0, today_date, today_weekday_ru)

            # 4. Анализ результатов
            stats = await self._analyze_results(all_updated_students, students_8_updated, target_date, is_saturday)

            # 5. Обновление дат оплаты
            payment_updates = await self.update_payment_dates(target_date)
            logger.info(f"✅ Обновлено дат оплаты: {payment_updates} студентов")

            # 6. Формирование отчета
            await self._generate_report(all_updated_students, students_8_updated, target_date, is_saturday,
                                        updated_count)

            return self._create_success_response(updated_count, payment_updates, stats, today_date, today_weekday_ru)

        except Exception as e:
            error_msg = f"💥 Критическая ошибка: {str(e)}"
            logger.error(error_msg)
            return self._create_response(False, error_msg, 0, 0)

    async def _analyze_results(self, all_students: List[Dict], tariff_8_students: List[Dict],
                               today_date: datetime, is_saturday: bool) -> Dict[str, int]:
        """Анализ результатов списания"""
        stats = {
            'special_tariff_count': 0,
            'regular_count': 0,
            'multiple_visits_count': 0,
            'negative_balance_count': 0,
            'tariff_8_count': len(tariff_8_students),
            'zero_balance_count': 0
        }

        for student in all_students:
            if student['classes_remaining'] < 0:
                stats['negative_balance_count'] += 1
                logger.warning(f"⚠️ Студент {student['name']} ушел в минус: {student['classes_remaining']}")
            elif student['classes_remaining'] == 0:
                stats['zero_balance_count'] += 1
                logger.info(f"ℹ️ Студент {student['name']} имеет нулевой баланс")

            if student not in tariff_8_students and is_saturday:
                if student['price'] in self.SPECIAL_TARIFFS:
                    stats['special_tariff_count'] += 1
                else:
                    visit_count = await self.get_visits_count(student['id'], today_date)
                    if visit_count > 1:
                        stats['multiple_visits_count'] += 1
                    else:
                        stats['regular_count'] += 1

        logger.info(f"✅ Списано занятий у {len(all_students)} студентов")

        if is_saturday:
            logger.info(
                f"🎯 По субботам: {stats['special_tariff_count']} по 2 занятия, "
                f"{stats['multiple_visits_count']} по количеству посещений, "
                f"{stats['regular_count']} по 1 занятию, "
                f"{stats['tariff_8_count']} с тарифом 8")

        if stats['negative_balance_count'] > 0:
            logger.warning(f"🔴 {stats['negative_balance_count']} студентов имеют отрицательный баланс!")
        if stats['zero_balance_count'] > 0:
            logger.info(f"🟡 {stats['zero_balance_count']} студентов имеют нулевой баланс")

        return stats

    async def _generate_report(self, all_students: List[Dict], tariff_8_students: List[Dict],
                               today_date: datetime, is_saturday: bool, total_count: int):
        """Генерация отчета по списаниям"""
        logger.info("📊 Отчет по списаниям:")
        for student in all_students[:5]:
            balance_status = "🔴 МИНУС" if student['classes_remaining'] < 0 else "🟢 НОРМА"

            if student in tariff_8_students:
                logger.info(
                    f"   👉 {student['name']} - тариф 8, осталось {student['classes_remaining']} {balance_status}")
            elif is_saturday and student['price'] in self.SPECIAL_TARIFFS:
                logger.info(
                    f"   👉 {student['name']} - списано 2 занятия, осталось {student['classes_remaining']} {balance_status}")
            elif is_saturday:
                visit_count = await self.get_visits_count(student['id'], today_date)
                logger.info(
                    f"   👉 {student['name']} - списано {visit_count} занятий, осталось {student['classes_remaining']} {balance_status}")
            else:
                logger.info(
                    f"   👉 {student['name']} - списано 1 занятие, осталось {student['classes_remaining']} {balance_status}")

        if total_count > 5:
            logger.info(f"   ... и еще {total_count - 5} студентов")

    def _create_response(self, success: bool, message: str, updated: int,
                         payment_updates: int, date: datetime = None, weekday: str = None) -> Dict:
        """Создание базового ответа"""
        response = {
            "success": success,
            "message": message,
            "updated": updated,
            "payment_dates_updated": payment_updates
        }
        if date and weekday:
            response.update({"date": date.isoformat(), "weekday": weekday})
        return response

    def _create_success_response(self, updated_count: int, payment_updates: int,
                                 stats: Dict, today_date: datetime, today_weekday_ru: str) -> Dict:
        """Создание успешного ответа"""
        null_balance_count = 0  # Можно добавить логику подсчета если нужно

        message_suffix = f", пропущено {null_balance_count} студентов с NULL балансом" if null_balance_count > 0 else ""

        response = {
            "success": True,
            "message": f"✅ Списано занятий у {updated_count} студентов, обновлено {payment_updates} дат оплаты{message_suffix}",
            "updated": updated_count,
            "payment_dates_updated": payment_updates,
            "date": today_date.isoformat(),
            "weekday": today_weekday_ru
        }
        response.update(stats)
        return response


async def main():
    """Основная функция для запуска через cron"""
    try:
        parser = argparse.ArgumentParser(description='Ежедневное списание занятий')
        parser.add_argument('--date', type=str, help='Дата для обработки в формате YYYY-MM-DD (по умолчанию сегодня)')
        args = parser.parse_args()

        target_date = datetime.fromisoformat(args.date) if args.date else datetime.now()
        logger.info(f"🎯 Обработка для даты: {target_date.date()}")

        logger.info("=" * 50)
        logger.info("🏁 НАЧАЛО ВЫПОЛНЕНИЯ СКРИПТА")

        processor = AttendanceProcessor()
        result = await processor.subtract_classes_and_update_payment_dates(target_date)

        logger.info(f"🏁 РЕЗУЛЬТАТ: {result['message']}")
        logger.info("=" * 50)

        sys.exit(0 if result['success'] else 1)

    except Exception as e:
        logger.error(f"💥 Фатальная ошибка: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())