import os
import sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print(project_root)
os.chdir(project_root)
sys.path.insert(0, project_root)

from sqlalchemy.orm import Session, sessionmaker


from database.schemas import engine

from sqlalchemy import text
from sqlalchemy.orm import Session


def calculate_trainer_salary_sql(db: Session, year: int = None, month: int = None):
    """
    Расчёт зарплаты тренеров через SQL запрос
    """
    sql_query = """
    SELECT 
        t.name as trainer_name,
        SUM(
            CASE 
                WHEN s.second_trainer_id IS NULL THEN p.price
                WHEN s.head_trainer_id = t.id THEN p.price - 900
                WHEN s.second_trainer_id = t.id THEN 900
                ELSE 0
            END
        ) as total_amount,
        (SUM(
            CASE 
                WHEN s.second_trainer_id IS NULL THEN p.price
                WHEN s.head_trainer_id = t.id THEN p.price - 900
                WHEN s.second_trainer_id = t.id THEN 900
                ELSE 0
            END
        ) * 0.368) as salary,
        COUNT(DISTINCT CASE WHEN s.head_trainer_id = t.id THEN s.id END) as main_trainer_students,
        COUNT(DISTINCT CASE WHEN s.second_trainer_id = t.id THEN s.id END) as second_trainer_students,
        COUNT(DISTINCT s.id) as total_students,
        TO_CHAR(pm.payment_date, 'YYYY-MM') as month
    FROM trainer t
    LEFT JOIN student s ON (s.head_trainer_id = t.id OR s.second_trainer_id = t.id)
    LEFT JOIN payment pm ON pm.student_id = s.id
    LEFT JOIN price p ON p.id = pm.price_id
    WHERE 
        pm.payment_date IS NOT NULL
        AND s.active = true
    """

    # Добавляем фильтр по году и месяцу если указаны
    if year and month:
        sql_query += """
        AND EXTRACT(YEAR FROM pm.payment_date) = :year 
        AND EXTRACT(MONTH FROM pm.payment_date) = :month
        """
        params = {'year': year, 'month': month}
    else:
        params = {}

    sql_query += """
    GROUP BY t.id, t.name, TO_CHAR(pm.payment_date, 'YYYY-MM')
    ORDER BY month DESC, salary DESC
    """

    # Выполняем запрос
    result = db.execute(text(sql_query), params)

    # Форматируем результат
    salary_data = []
    for row in result:
        salary_data.append({
            'trainer_name': row.trainer_name,
            'total_amount': float(row.total_amount or 0),
            'salary': float(row.salary or 0),
            'main_trainer_students': row.main_trainer_students or 0,
            'second_trainer_students': row.second_trainer_students or 0,
            'total_students': row.total_students or 0,
            'month': row.month
        })

    return salary_data


def calculate_trainer_salary_all_months(db: Session):
    """
    Расчёт зарплаты за все месяцы
    """
    return calculate_trainer_salary_sql(db)


def calculate_trainer_salary_for_month(db: Session, year: int, month: int):
    """
    Расчёт зарплаты за конкретный месяц
    """
    return calculate_trainer_salary_sql(db, year, month)


# Пример использования
if __name__ == "__main__":

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        # Вариант 1: За все месяцы
        # print("Зарплата за все месяцы:")
        # all_salaries = calculate_trainer_salary_all_months(db)
        # for data in all_salaries:
        #     print(f"Тренер: {data['trainer_name']}")
        #     print(f"  Месяц: {data['month']}")
        #     print(f"  Общая сумма: {data['total_amount']:.2f} руб.")
        #     print(f"  Зарплата: {data['salary']:.2f} руб.")
        #     print(
        #         f"  Ученики: всего {data['total_students']} (главный: {data['main_trainer_students']}, второй: {data['second_trainer_students']})")
        #     print()

        # Вариант 2: За конкретный месяц
        print("\n" + "=" * 50)
        month_salaries = calculate_trainer_salary_for_month(db, 2025, 11)
        for data in month_salaries:
            print(f"Тренер: {data['trainer_name']}")
            print(f"  Месяц: {data['month']}")
            print(f"  Общая сумма: {data['total_amount']:.2f} руб.")
            print(f"  Зарплата: {data['salary']:.2f} руб.")
            print(
                f"  Ученики: всего {data['total_students']} (главный: {data['main_trainer_students']}, второй: {data['second_trainer_students']})")
            print()

    finally:
        db.close()
