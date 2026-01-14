import configparser
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
import os
from typing import Dict, Any
from fastapi.templating import Jinja2Templates

# Загружаем переменные окружения
load_dotenv()

# Читаем конфигурационный файл
config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')

# Получаем секретный ключ из переменных окружения
SECRET = os.environ.get("SECRET_KEY")

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


class JWTConfig(BaseSettings):
    """Конфигурация JWT для локальной авторизации"""
    secret_key: str = SECRET or "fallback-secret-key-change-me-in-production"  # Устанавливаем дефолтное значение
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7


class AuthConfig(BaseSettings):
    """Конфигурация авторизации"""
    enable_local_auth: bool = True  # Включить локальную аутентификацию
    enable_superset_auth: bool = True  # Включить Superset аутентификацию
    default_auth_method: str = "superset"  # superset или local


class Settings(BaseSettings):
    db: DB = DB()
    tg: Tg = Tg()
    redis_conf: Redis_conf = Redis_conf()
    superset_conf: Superset_conf = Superset_conf()
    jwt: JWTConfig = JWTConfig()
    auth: AuthConfig = AuthConfig()

    # Дополнительные настройки
    debug: bool = os.environ.get("DEBUG", "False").lower() == "true"


settings = Settings()

# Создаем папку templates если её нет
if not os.path.exists("templates"):
    os.makedirs("templates")

# Инициализируем templates для использования во всех роутерах
templates = Jinja2Templates(directory="templates")