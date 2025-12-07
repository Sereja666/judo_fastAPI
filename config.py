import configparser
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
import os
from typing import Dict, Any
from fastapi.templating import Jinja2Templates

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
    REDIS_HOST: str = config['redis']['REDIS_HOST']
    REDIS_PORT: str = config['redis']['REDIS_PORT']
    REDIS_DB: int = int(config['redis']['REDIS_DB'])


class Superset_conf(BaseSettings):
    base_url: str = config['superset']["SUPERSET_BASE_URL"]


class Tg(BaseSettings):
    token_notif: str = config['tg']["TOKEN_notif"]
    token_admin: str = config['tg']["TOKEN_admin"]
    root_pass: str = config['tg']["ROOT_PASS"]


class Settings(BaseSettings):
    db: DB = DB()
    tg: Tg = Tg()
    redis_conf: Redis_conf = Redis_conf()
    superset_conf: Superset_conf = Superset_conf()


settings = Settings()

# Создаем папку templates если её нет
if not os.path.exists("templates"):
    os.makedirs("templates")

# Инициализируем templates для использования во всех роутерах
templates = Jinja2Templates(directory="templates")
