from sqlalchemy.orm import sessionmaker
from datetime import datetime
import pandas as pd
from sqlalchemy import and_

from database.models import engine, Students


def student_exists(session, name: str, birthday: datetime) -> bool:
    """Проверяет, существует ли студент с такими ФИО и датой рождения"""
    return session.query(Students).filter(
        and_(
            Students.name == name,
            Students.birthday == birthday
        )
    ).first() is not None


def add_student_with_check(engine, student_data: dict) -> int:
    """
    Добавляет студента с проверкой на дубликаты
    Возвращает ID существующего или нового студента
    """
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Проверяем существование студента
        if student_exists(session, student_data['name'], student_data['birthday']):
            existing = session.query(Students).filter(
                and_(
                    Students.name == student_data['name'],
                    Students.birthday == student_data['birthday']
                )
            ).first()
            print(f"Студент {student_data['name']} уже существует (ID {existing.id})")
            return existing.id

        # Если дубликата нет - создаем нового
        new_student = Students(**student_data)
        session.add(new_student)
        session.commit()
        print(f"Добавлен новый студент {student_data['name']} (ID {new_student.id})")
        return new_student.id

    except Exception as e:
        session.rollback()
        print(f"Ошибка при добавлении студента: {e}")
        return None
    finally:
        session.close()


# # Пример данных
# student_data = {
#     'full_name': 'Иванов Петр Сидорович',
#     'birthday': datetime(2010, 5, 15),
#     'sport_discipline': 2,
#     'rang': '3 юн.',
#     'sex': 'М',
#     'weight': 45,
#     'telephone': '+79161234567',
#     'reference1': datetime(2024, 12, 31),
#     'price': 3500,
#     'date_start': datetime(2023, 9, 1),
#     'telegram_id': 123456789
# }
#
# # Вызов функции
# student_id = add_student(engine, **student_data)
#
# if student_id:
#     print(f"Создан студент с ID {student_id}")

# Обработка Excel-файла с проверкой дублей
df = pd.read_excel(r'C:\Python\Judo_aiogram_superset\data\11.xlsx', sheet_name='Лист5')

for index, row in df.iterrows():
    student_data = {
        'name': row['ФИО'],
        'birthday': row['Дата рождения'] if isinstance(row['Дата рождения'], datetime)
        else datetime.strptime(row['Дата рождения'], '%d.%m.%Y'),
        'sport_discipline': 3,
        # "date_start": datetime(int(row['Год начала']), 1, 1) ,
        'sex' : row['пол']
        # остальные поля по необходимости
    }

    student_id = add_student_with_check(engine, student_data)
