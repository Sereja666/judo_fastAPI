from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from database.schemas import Telegram_user


def update_telegram_user_orm(user_data, connection_string):
    """
    Обновляет запись в таблице telegram_user используя SQLAlchemy ORM

    Args:
        user_data (dict): Словарь с данными для обновления
                         Должен содержать 'telegram_id' для идентификации
        connection_string (str): Строка подключения к БД

    Returns:
        bool: True если обновление прошло успешно, False в случае ошибки
    """
    try:
        # Создаем подключение
        engine = create_engine(connection_string)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Получаем telegram_id
        telegram_id = user_data.get('telegram_id')
        if not telegram_id:
            raise ValueError("Словарь должен содержать ключ 'telegram_id'")

        # Находим пользователя
        user = session.query(Telegram_user).filter_by(telegram_id=telegram_id).first()
        if not user:
            print(f"Пользователь с telegram_id {telegram_id} не найден")
            return False

        # Обновляем поля
        update_fields = [
            'permissions', 'telegram_username', 'refer_id', 'date_reg',
            'phone', 'password_hash', 'email', 'full_name', 'is_active', 'last_login'
        ]

        updated = False
        for field in update_fields:
            if field in user_data and user_data[field] is not None:
                setattr(user, field, user_data[field])
                updated = True

        # Автоматически обновляем last_login при определенных условиях
        if 'last_login' not in user_data and any(field in user_data for field in ['phone', 'password_hash']):
            user.last_login = datetime.now()

        if updated:
            session.commit()
            print(f"Пользователь {telegram_id} успешно обновлен")
            return True
        else:
            print("Нет данных для обновления")
            return False

    except Exception as e:
        session.rollback()
        print(f"Ошибка при обновлении пользователя: {e}")
        return False
    finally:
        session.close()




data = {'telegram_id': '5255683105',
        'phone': "+79183249979",
        'permissions': 99,
        'telegram_username': "Администратор Ставрапольская"}

PG_LINK="postgresql+psycopg2://superset:superset@10.10.10.28:5433/superset"
update_telegram_user_orm(data, PG_LINK)