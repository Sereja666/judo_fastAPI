from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from sqlalchemy import create_engine, Column, Integer, String, MetaData, Date, Boolean, ForeignKey, DateTime, Time, \
    BigInteger, UniqueConstraint
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.sql import func
from config import settings

engine = create_engine(settings.db.db_url, connect_args={"options": "-c timezone=Europe/Moscow"})
engine_async = create_async_engine(
    settings.db.db_url_asinc,
    echo=True,  # Включите для отладки SQL запросов
    pool_pre_ping=True,  # Проверять соединение перед использованием
    pool_recycle=3600,  # Пересоздавать соединение каждые 3600 секунд
)
Base = declarative_base()
metadata = MetaData()

schema = 'public'

# Создаем сессию базы данных
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Зависимость для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Асинхронная фабрика сессий
AsyncSessionLocal = async_sessionmaker(
    engine_async,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@asynccontextmanager
async def get_db_async():
    """Асинхронный генератор сессий БД"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Посещения
class Visits(Base):
    __tablename__ = 'visit'
    __table_args__ = {'schema': schema}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    data = Column(DateTime())
    trainer = Column(Integer())
    student = Column(Integer())
    place = Column(Integer())
    sport_discipline = Column(Integer())
    shedule = Column(Integer())


# Посещения
class Lesson_write_offs(Base):
    __tablename__ = 'lesson_write_offs'
    __table_args__ = {'schema': schema}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    data = Column(DateTime())
    student_id = Column(Integer())
    quantity = Column(Integer())


# Ученики
class Students(Base):
    __tablename__ = 'student'
    __table_args__ = {'schema': schema}

    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String())
    birthday = Column(DateTime())
    sport_discipline = Column(Integer())
    rang = Column(Integer())  # ID из Belt_сolor
    sports_rank = Column(Integer())  # id sports_rank
    sex = Column(String())
    weight = Column(Integer())
    head_trainer_id = Column(Integer())  # айди главного тренера
    second_trainer_id = Column(Integer())  # айди второго тренера
    price = Column(Integer(), default=0, server_default='0')
    payment_day = Column(Integer())  # день месяца для оплаты (1-31)
    classes_remaining = Column(Integer())  # сколько занятий на остатке в этом месяце
    expected_payment_date = Column(Date())  # ожидаемая дата оплаты
    telephone = Column(String())
    parent1 = Column(Integer())
    parent2 = Column(Integer())
    date_start = Column(DateTime())  # дата начала тренеровок
    telegram_id = Column(Integer())
    active = Column(Boolean(), default=True, server_default='true')


# Связь ученики-расписание
class Students_schedule(Base):
    __tablename__ = 'student_schedule'
    __table_args__ = {'schema': schema}

    id = Column(Integer(), primary_key=True, autoincrement=True)
    student = Column(Integer())
    schedule = Column(Integer())


# Связь ученики-родители
class Students_parents(Base):
    __tablename__ = 'students_parents'
    __table_args__ = {'schema': schema}

    id = Column(Integer(), primary_key=True, autoincrement=True)
    student = Column(Integer())  # student.id
    parents = Column(Integer())  # tg_notif_user.id


# Тренера
class Trainers(Base):
    __tablename__ = 'trainer'
    __table_args__ = {'schema': schema}

    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String())
    sex = Column(String())
    birthday = Column(DateTime())
    sport_discipline = Column(Integer())
    telephone = Column(String())
    telegram_id = Column(BigInteger())
    active = Column(Boolean(), default=True, server_default='true')


# Родители
class Parents(Base):
    __tablename__ = 'parent'
    __table_args__ = {'schema': schema}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String())
    telephone = Column(String())
    children = Column(Integer())


# Прайс-лист занятий
class Prices(Base):
    __tablename__ = 'price'
    __table_args__ = {'schema': schema}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    price = Column(Integer())
    classes_in_price = Column(Integer())  # количество занятий по прайсу
    description = Column(String())


# Факт оплаты
class Payment(Base):
    """
    Факт оплаты
    """
    __tablename__ = 'payment'
    __table_args__ = {'schema': schema}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    student_id = Column(Integer())
    price_id = Column(Integer())
    payment_amount = Column(Integer())
    payment_date = Column(Date())


class BalanceLog(Base):
    """Логи изменений баланса занятий"""
    __tablename__ = 'balance_log'
    __table_args__ = {'schema': schema}

    id = Column(Integer(), primary_key=True, autoincrement=True)
    student_id = Column(Integer(), ForeignKey(f'{schema}.student.id'))
    old_balance = Column(Integer())
    new_balance = Column(Integer())
    difference = Column(Integer())  # new_balance - old_balance
    reason = Column(String())  # Причина изменения
    changed_by = Column(Integer())  # ID пользователя, который изменил
    changed_at = Column(DateTime(), default=func.now())
    # Связи
    student = relationship("Students", backref="balance_logs")


# Расписание
class Schedule(Base):
    """
        Расписание
        """
    __tablename__ = 'schedule'
    __table_args__ = {'schema': schema}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    day_week = Column(String())
    time_start = Column(Time())
    time_end = Column(Time())
    training_place = Column(Integer())
    sport_discipline = Column(Integer())
    description = Column(String())


# Залы тренировок
class Training_place(Base):
    """
    Залы тренировок
    """
    __tablename__ = 'training_place'
    __table_args__ = {'schema': schema}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String())
    address = Column(String())


# Спортивные дисциплины
class Sport(Base):
    __tablename__ = 'sport'
    __table_args__ = {'schema': schema}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String())


class Sports_rank(Base):
    """спортивные разряды и звания"""
    __tablename__ = 'sport_rank'
    __table_args__ = {'schema': schema}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    rank = Column(String())


class Belt_сolor(Base):
    __tablename__ = 'belt_color'
    __table_args__ = {'schema': schema}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String())
    color = Column(String())


class Telegram_user(Base):
    __tablename__ = 'telegram_user'
    __table_args__ = {'schema': schema}

    telegram_id = Column(BigInteger(), primary_key=True)
    permissions = Column(Integer(), default=0)
    telegram_username = Column(String())
    refer_id = Column(Integer())
    date_reg = Column(DateTime())

    # Добавляем поля для обычной авторизации
    phone = Column(String(), unique=True)  # Уникальный номер телефона
    password_hash = Column(String())  # Хеш пароля
    email = Column(String())  # Email (опционально)
    full_name = Column(String())  # Полное имя
    last_login = Column(DateTime())  # Дата последнего входа

    is_active = Column(Boolean(), default=True, server_default='true')


class Tg_notif_user(Base):
    __tablename__ = 'tg_notif_user'
    __table_args__ = {'schema': schema}

    id = Column(Integer(), primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger())
    permissions = Column(Integer(), default=0)
    telegram_username = Column(String())
    refer_id = Column(Integer())
    date_reg = Column(DateTime())

    # Добавляем поля для обычной авторизации
    phone = Column(String(), unique=True)  # Уникальный номер телефона
    password_hash = Column(String())  # Хеш пароля
    email = Column(String())  # Email (опционально)
    full_name = Column(String())  # Полное имя
    last_login = Column(DateTime())  # Дата последнего входа

    # Поля разрешения
    get_news = Column(Boolean(), default=False, server_default='false')
    get_pays_notif = Column(Boolean(), default=False, server_default='false')
    get_info_student = Column(Boolean(), default=False, server_default='false')

    is_active = Column(Boolean(), default=True, server_default='true')


# Права телеграма
class Telegram_permissions(Base):
    __tablename__ = 'telegram_permission'
    __table_args__ = {'schema': schema}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String())


# Не используется пока
class Subscription(Base):
    __tablename__ = 'subscription'
    __table_args__ = {'schema': schema}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String())


# Соревнования
class Сompetition(Base):
    """
    Соревнования
    """
    __tablename__ = 'competition'
    __table_args__ = {'schema': schema}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String())
    address = Column(String())
    date = Column(DateTime())


class Competition_student(Base):
    """
    ПРиглашение на соревнования участников
    """
    __tablename__ = 'competition_student'
    __table_args__ = (
        UniqueConstraint('competition_id', 'student_id', name='uq_competition_student'),
        {'schema': schema}
    )
    id = Column(Integer(), primary_key=True, autoincrement=True)
    competition_id = Column(Integer())
    student_id = Column(Integer())
    participation = Column(Integer(), default=0)  # 0-необработанно, 1-отправлено,  2-принято, 3-отклонено
    status_id = Column(Integer(), default=0)  # ожидание 0 / место 1,2,3,4,5,  / пропуск 98, проиграл - 99


class Сompetition_trainer(Base):
    """
    Ответственный за соревнование тренер
    """
    __tablename__ = 'competition_trainer'
    __table_args__ = {'schema': schema}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    competition_id = Column(Integer())
    trainer_id = Column(Integer())


class Сompetition_referee(Base):
    """
    Ответственный за соревнование судья
    """
    __tablename__ = 'competition_referee'
    __table_args__ = {'schema': schema}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    competition_id = Column(Integer())
    student_id = Column(Integer()) # приглашённый ученик в качестве тренера


class Сompetition_MedCertificat(Base):
    """
    Справки для соревнования
    """
    __tablename__ = 'competition_medcert'
    __table_args__ = {'schema': schema}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    competition_id = Column(Integer())
    med_certificat_id = Column(Integer())


class MedCertificat_type(Base):
    """
    Типы медицинских справок (допусков)
    """
    __tablename__ = 'medcertificat_type'  # Измените на нижний регистр
    __table_args__ = {'schema': schema}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    name_cert = Column(String())


# Факт получения справки

class MedCertificat_received(Base):
    """
    Факт получения справки (разрешалки)
    """
    __tablename__ = 'medcertificat_received'
    __table_args__ = {'schema': schema}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    student_id = Column(Integer())
    cert_id = Column(Integer())  # id справки из medcertificat_type
    date_start = Column(Date())  # начало справки
    date_end = Column(Date())  # окончание справки
    active = Column(Boolean(), default=True, server_default='true')  # актуальность справки


class MedicalCertificates(Base):
    """
    История справок по болезни
    """
    __tablename__ = 'medical_certificates'
    __table_args__ = {'schema': schema}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    student_id = Column(Integer())
    start_date = Column(Date())
    end_date = Column(Date())
    missed_classes = Column(Integer())
    added_classes = Column(Integer())
    processed_date = Column(Date())



if __name__ == "__main__":
    Base.metadata.create_all(engine)
