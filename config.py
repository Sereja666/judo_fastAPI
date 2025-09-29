import configparser
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
import os
from typing import Dict, Any
# BASE_DIR = Path(__file__).parent

config = configparser.ConfigParser()
config.sections()
config.read('C:\Python\Judo_aiogram_superset\config.ini', encoding='utf-8')

load_dotenv()

DB_HOST = os.environ.get("DB_HOST")
DB_PORT = os.environ.get("DB_PORT")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
SECRET = os.environ.get("SECRET")
PG_LINK = {
    "user": "superset",
    "password": "superset",
    "database": "superset",
    "host": "10.10.10.28",
    "port": "5433"
}

class DB(BaseSettings):
    user: str = config['db']['user']
    password: str = config['db']['password']
    host: str = config['db']['host']
    port: str = config['db']['port']
    db: str = config['db']['dbname']

    # db_url: str = f'postgresql+psycopg2://{user}:{password}@172.19.38.68:5433/superset'
    # url: str = f'postgresql+psycopg2://{user}:{password}@localhost:5432/superset_judo'

    db_url: str = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    db_url_asinc: str = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"
    @property
    def pg_link(self) -> Dict[str, Any]:
        return PG_LINK

class Redis_conf(BaseSettings):
    # Добавьте настройки Redis
    REDIS_HOST: str = config['redis']['REDIS_HOST']
    REDIS_PORT: str = config['redis']['REDIS_PORT']
    REDIS_DB: int = int(config['redis']['REDIS_DB'])


class Settings(BaseSettings):
    db: DB = DB()
    redis_conf: Redis_conf = Redis_conf()


settings = Settings()
