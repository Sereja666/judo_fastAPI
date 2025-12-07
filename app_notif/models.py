import sys
import os

from database.models import Tg_notif_user

# Добавляем путь к основному проекту
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

# Импортируем модели из основного проекта


# Создаем алиас для удобства
User = Tg_notif_user