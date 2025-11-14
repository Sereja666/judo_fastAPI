import configparser
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
import os
from typing import Dict, Any
# BASE_DIR = Path(__file__).parent

config = configparser.ConfigParser()
config.sections()
config.read('config.ini', encoding='utf-8')

load_dotenv()

SECRET = os.environ.get("SECRET")

PG_LINK = {
    "user": config['db']['user'],
    "password": config['db']['password'],
    "database": config['db']['dbname'],
    "host": config['db']['host'],
    "port": config['db']['port']
}

class DB(BaseSettings):
    user: str = config['db']['user']
    password: str = config['db']['password']
    host: str = config['db']['host']
    port: str = config['db']['port']
    db: str = config['db']['dbname']


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

class Superset_conf(BaseSettings):
    # Добавьте настройки Redis
    base_url: str = config['superset']["SUPERSET_BASE_URL"]


class Settings(BaseSettings):
    db: DB = DB()
    redis_conf: Redis_conf = Redis_conf()
    superset_conf : Superset_conf = Superset_conf()


settings = Settings()
