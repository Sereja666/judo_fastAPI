from datetime import datetime

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from config import settings
from database.models import Visits
from db_handler.db_funk import execute_raw_sql


# engine = create_async_engine(settings.db.db_url, echo=True, connect_args={"options": "-c timezone=Europe/Moscow"})
# async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# async def get_data():
#     async with async_session() as session:
#         result = await session.execute("SELECT * FROM training_place")
#         return result.fetchall()

# Зависимость для получения сессии БД


async def save_selection(schedule_id: int, student_ids: list):
    """
    Усовершенствованная версия с проверками
    :param schedule_id: ID расписания
    :param student_ids: Список ID студентов
    :return: Tuple (success: bool, message: str)
    """
    try:
        if not student_ids:
            return False, "Нет студентов для сохранения"

        # Проверяем существование расписания
        schedule_exists = await execute_raw_sql(
            f"SELECT 1 FROM big_db.schedule WHERE id = {schedule_id};"
        )
        if not schedule_exists:
            return False, "Расписание не найдено"

        # Проверяем существование студентов
        existing_students = await execute_raw_sql(
            f"SELECT id FROM big_db.student WHERE id IN ({','.join(map(str, student_ids))});"
        )
        existing_ids = {s['id'] for s in existing_students}
        missing_ids = set(student_ids) - existing_ids

        if missing_ids:
            print(f"Не найдены студенты: {missing_ids}")

        # Вставляем только существующих студентов
        success_count = 0
        for student_id in existing_ids:
            try:
                await execute_raw_sql(
                    f"INSERT INTO big_db.student_attendance "
                    f"(schedule_id, student_id, attended, created_at) "
                    f"VALUES ({schedule_id}, {student_id}, TRUE, NOW()) "
                    f"ON CONFLICT (schedule_id, student_id) DO UPDATE "
                    f"SET attended = EXCLUDED.attended, updated_at = NOW();"
                )
                success_count += 1
            except Exception as e:
                print(f"Error saving student {student_id}: {e}")

        return True, f"Сохранено {success_count} из {len(student_ids)} студентов"

    except Exception as e:
        print(f"Database error in save_selection: {e}")
        return False, "Ошибка базы данных"


async def create_db_session():
    DATABASE_URL = settings.db.db_url_asinc
    engine = create_async_engine(DATABASE_URL)
    return async_sessionmaker(engine, expire_on_commit=False)


async def setup_db():
    # Создаем асинхронный engine
    engine = create_async_engine(
        settings.db.db_url_asinc,
        echo=True,  # Логирование запросов (можно отключить в production)
        pool_size=5,
        max_overflow=10
    )

    # Создаем фабрику сессий
    async_session = sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession
    )

    return async_session


async def create_visit_record_model(
    session: AsyncSession,
    visit_datetime: datetime,
    trainer_id: int,
    student_id: int,
    place_id: int,
    discipline_id: int,
    schedule_id: int
):
    new_visit = Visits(
        data=visit_datetime,
        trainer=trainer_id,
        student=student_id,
        place=place_id,
        sport_discipline=discipline_id,
        shedule=schedule_id
    )
    session.add(new_visit)
    await session.commit()
    return new_visit