from datetime import datetime, timedelta

from sqlalchemy import create_engine, Column, Integer, String, MetaData, Date, Boolean, ForeignKey, DateTime, Time
from sqlalchemy.orm import declarative_base, relationship

from config import settings

engine = create_engine(settings.db.db_url, connect_args={"options": "-c timezone=Europe/Moscow"})
Base = declarative_base()
metadata = MetaData()

schema = 'public'


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


# Ученики
class Students(Base):
    __tablename__ = 'student'
    __table_args__ = {'schema': schema}

    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String())
    birthday = Column(DateTime())
    sport_discipline = Column(Integer())
    rang = Column(String())
    sex = Column(String())
    weight = Column(Integer())
    reference1 = Column(Date())  # до какого числа действует справка
    reference2 = Column(Date())  # до какого числа действует справка
    reference3 = Column(Date())  # до какого числа действует справка
    price = Column(Integer())
    payment_day = Column(Integer())  # день месяца для оплаты (1-31)
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
    telegram_id = Column(Integer())


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
    description = Column(String())


# Факт оплаты
class Payment(Base):
    __tablename__ = 'payment'
    __table_args__ = {'schema': schema}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    student_id = Column(Integer())
    price_id = Column(Integer())
    payment_amount = Column(Integer())
    payment_date = Column(Date())


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


# Пользователи телеграма
class Telegram_user(Base):
    __tablename__ = 'telegram_user'
    __table_args__ = {'schema': schema}
    telegram_id = Column(Integer(), primary_key=True)
    permissions = Column(Integer())
    telegram_username = Column(String())
    refer_id = Column(Integer())
    date_reg = Column(DateTime())


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


# Залы тренировок
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


class Сompetition_student(Base):
    """
    ПРиглашение на соревнования участников
    """
    __tablename__ = 'competition_student'
    __table_args__ = {'schema': schema}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    competition_id = Column(Integer())
    student_id = Column(Integer())
    status_id = Column(Integer(), default=0) # ожидание 0 / место 1,2,3,4,5,  / пропуск 98, проиграл - 99


class Сompetition_trainer(Base):
    """
    Ответственный тренер
    """
    __tablename__ = 'competition_trainer'
    __table_args__ = {'schema': schema}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    competition_id = Column(Integer())
    trainer_id = Column(Integer())


if __name__ == "__main__":
    Base.metadata.create_all(engine)
