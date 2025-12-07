
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import sys
import os

# Добавляем путь к основному проекту для импорта schemas
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from config import settings

# Используем ту же базу данных, что и основной проект
SQLALCHEMY_DATABASE_URL = settings.db.db_url

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"options": "-c timezone=Europe/Moscow"}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
