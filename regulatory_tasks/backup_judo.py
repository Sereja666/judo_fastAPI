import os
import subprocess
import datetime
import shutil
from config import PG_LINK


def create_docker_superset_backup():
    """
    Бэкап PostgreSQL работающего в Docker контейнере
    """

    # Конфигурация
    DOCKER_CONTAINER = "big_db"  # Имя контейнера


    BACKUP_PATH = r"/mnt/backup_judo"

    # Проверяем сетевую папку
    if not os.path.exists(BACKUP_PATH):
        print(f"❌ Сетевая папка недоступна: {BACKUP_PATH}")
        return None

    # Создаем имя файла
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"superset_docker_{timestamp}.sql"
    backup_filepath = os.path.join(BACKUP_PATH, backup_filename)

    try:
        print("🔄 Создание бэкапа из Docker контейнера...")

        # Команда для выполнения pg_dump внутри контейнера
        cmd = [
            "docker", "exec", DOCKER_CONTAINER,
            "pg_dump",
            "-h", PG_LINK["host"],
            "-p", PG_LINK["port"],
            "-U", PG_LINK["user"],
            "-d", PG_LINK["dbname"],
            "-w"
        ]

        # Устанавливаем пароль
        env = os.environ.copy()
        env['PGPASSWORD'] = PG_LINK['password']

        # Выполняем и сохраняем в файл
        with open(backup_filepath, 'w') as f:
            result = subprocess.run(
                cmd,
                env=env,
                stdout=f,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )

        # Сжимаем файл
        compressed_filepath = backup_filepath + ".gz"
        compress_cmd = ["gzip", backup_filepath]
        subprocess.run(compress_cmd, check=True)

        file_size = os.path.getsize(compressed_filepath) / (1024 * 1024)

        print(f"✅ Бэкап успешно создан!")
        print(f"📁 Файл: {compressed_filepath}")
        print(f"📊 Размер: {file_size:.2f} MB")

        return compressed_filepath

    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при создании бэкапа:")
        print(f"Ошибка: {e.stderr}")
        return None
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return None


# Для запуска просто вызовите:
if __name__ == "__main__":
    backup_file = create_docker_superset_backup()