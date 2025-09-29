from sqlalchemy import create_engine, MetaData, Table, select
from sqlalchemy.orm import sessionmaker

from config import settings


def copy_table_between_schemas(
        engine,
        table_name: str,
        source_schema: str,
        target_schema: str,
        chunk_size: int = 1000,
        truncate_target: bool = False
):
    """
    Копирует данные между таблицами в разных схемах

    :param engine: SQLAlchemy engine
    :param table_name: Название таблицы (без схемы)
    :param source_schema: Исходная схема
    :param target_schema: Целевая схема
    :param chunk_size: Размер пачки для batch-вставки
    :param truncate_target: Очищать целевую таблицу перед копированием
    """
    Session = sessionmaker(bind=engine)
    session = Session()
    metadata = MetaData()

    try:
        # Получаем объекты таблиц
        source_table = Table(
            table_name,
            metadata,
            autoload_with=engine,
            schema=source_schema
        )

        target_table = Table(
            table_name,
            metadata,
            autoload_with=engine,
            schema=target_schema
        )
        print(f"Копирование данных из {source_schema}.{table_name} в {target_schema}.{table_name}")
        # Очистка целевой таблицы (если нужно)
        if truncate_target:
            session.execute(target_table.delete())
            session.commit()
            print(f"Таблица {target_schema}.{table_name} очищена")

        # Получаем все данные из исходной таблицы
        query = select(source_table)
        result_proxy = session.execute(query)
        print( " # Вставляем данные пачками")
        # Вставляем данные пачками
        total_rows = 0
        while True:
            chunk = result_proxy.fetchmany(chunk_size)
            if not chunk:
                break

            # Формируем список словарей для batch-вставки
            rows_to_insert = [dict(row._mapping) for row in chunk]

            # Вставляем пачку
            session.execute(target_table.insert(), rows_to_insert)
            session.commit()

            total_rows += len(chunk)
            print(f"Скопировано {total_rows} строк...", end='\r')

        print(
            f"\nГотово! Всего скопировано {total_rows} строк из {source_schema}.{table_name} в {target_schema}.{table_name}")
        return total_rows

    except Exception as e:
        session.rollback()
        print(f"Ошибка при копировании: {e}")
        return None
    finally:
        session.close()


# Создаем подключение
engine = create_engine(settings.db.db_url)

# Копируем таблицу 'students' из схемы 'schema1' в 'schema2'
copy_table_between_schemas(
    engine=engine,
    table_name="subscription",
    source_schema="big_db_old",
    target_schema="big_db",
    truncate_target=False  # Очистить целевую таблицу перед копированием
)