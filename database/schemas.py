from datetime import datetime, timedelta

from sqlalchemy import create_engine, Column, Integer, String, MetaData, Date, Boolean, ForeignKey, DateTime, Time
from sqlalchemy.orm import declarative_base, relationship

from config import settings

engine = create_engine(settings.db.db_url, connect_args={"options": "-c timezone=Europe/Moscow"})
Base = declarative_base()
metadata = MetaData()


class Visits(Base):
    __tablename__ = 'visit'
    __table_args__ = {'schema': 'public'}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    data = Column(DateTime())
    trainer = Column(Integer())
    student = Column(Integer())
    place = Column(Integer())
    sport_discipline = Column(Integer())
    shedule = Column(Integer())


class Students(Base):
    __tablename__ = 'student'
    __table_args__ = {'schema': 'public'}

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
    telephone = Column(String())
    start_subscription = Column(Date())  # до какого числа действует справка
    parent1 = Column(Integer())
    parent2 = Column(Integer())

class Students_schedule(Base):
    __tablename__ = 'student_schedule'
    __table_args__ = {'schema': 'public'}

    id = Column(Integer(), primary_key=True, autoincrement=True)
    student = Column(Integer())
    schedule = Column(Integer())

class Trainers(Base):
    __tablename__ = 'trainer'
    __table_args__ = {'schema': 'public'}

    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String())
    sex = Column(String())
    birthday = Column(DateTime())
    sport_discipline = Column(Integer())
    telephone = Column(String())
    telegram_id = Column(Integer())


class Parents(Base):
    __tablename__ = 'parent'
    __table_args__ = {'schema': 'public'}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String())
    telephone = Column(String())
    children = Column(Integer())


class Prices(Base):
    __tablename__ = 'price'
    __table_args__ = {'schema': 'public'}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    price = Column(Integer())
    description = Column(String())


class Schedule(Base):
    __tablename__ = 'schedule'
    __table_args__ = {'schema': 'public'}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    day_week = Column(String())
    time_start = Column(Time())
    time_end = Column(Time())
    training_place = Column(Integer())
    sport_discipline = Column(Integer())
    description = Column(String())





class Training_place(Base):
    __tablename__ = 'training_place'
    __table_args__ = {'schema': 'public'}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String())
    address = Column(String())


class Sport(Base):
    __tablename__ = 'sport'
    __table_args__ = {'schema': 'public'}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String())


class Telegram_user(Base):
    __tablename__ = 'telegram_user'
    __table_args__ = {'schema': 'public'}
    telegram_id = Column(Integer(), primary_key=True)
    permissions = Column(Integer())
    telegram_username = Column(String())
    refer_id = Column(Integer())
    date_reg = Column(DateTime())


class Telegram_permissions(Base):
    __tablename__ = 'telegram_permission'
    __table_args__ = {'schema': 'public'}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String())


class Subscription(Base):
    __tablename__ = 'subscription'
    __table_args__ = {'schema': 'public'}
    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String())

if __name__ == "__main__":
    Base.metadata.create_all(engine)
