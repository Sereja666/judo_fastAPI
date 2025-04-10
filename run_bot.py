import os
import subprocess

# Путь к скрипту aiogram_run.py
base_dir = 'C:\Python\Judo_aiogram_superset'
script_name = 'aiogram_run.py'
script_path = os.path.join(base_dir, script_name)

# Запуск настроенного виртуального окружения и бота
if os.path.exists(script_path):
    subprocess.run([r'C:\Python\Judo_aiogram_superset\venv\Scripts\python', script_path], check=True)
else:
    print("Не удалось найти скрипт aiogram_run.py.")
