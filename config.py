import configparser
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
import os

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


class DB(BaseSettings):
    user: str = config['db']['user']
    password: str = config['db']['password']
    host: str = config['db']['host']
    port: str = config['db']['port']
    db: str = config['db']['dbname']

    # db_url: str = f'postgresql+psycopg2://{user}:{password}@172.19.38.68:5433/superset'
    # url: str = f'postgresql+psycopg2://{user}:{password}@localhost:5432/superset_judo'

    db_url: str = f"postgresql://{user}:{password}@{host}:{port}/{db}"


class Settings(BaseSettings):
    db: DB = DB()


settings = Settings()
