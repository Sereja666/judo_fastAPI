import json
import redis
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class RedisStorage:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def _get_user_key(self, user_id: int) -> str:
        return f"bot:user:{user_id}:selected_students"

    def _get_session_key(self, user_id: int, session_id: str = "default") -> str:
        return f"bot:session:{user_id}:{session_id}"

    async def get_selected_students(self, user_id: int) -> Dict[str, str]:
        """Получить выбранных студентов для пользователя"""
        try:
            key = self._get_user_key(user_id)
            data = self.redis.get(key)
            return json.loads(data) if data else {}
        except Exception as e:
            logger.error(f"Error getting selected students for user {user_id}: {e}")
            return {}

    async def set_selected_students(self, user_id: int, students: Dict[str, str], ttl: int = 3600):
        """Сохранить выбранных студентов для пользователя"""
        try:
            key = self._get_user_key(user_id)
            self.redis.setex(key, ttl, json.dumps(students))
        except Exception as e:
            logger.error(f"Error setting selected students for user {user_id}: {e}")

    async def add_student(self, user_id: int, student_id: str, student_name: str):
        """Добавить студента в выбор"""
        students = await self.get_selected_students(user_id)
        students[student_id] = student_name
        await self.set_selected_students(user_id, students)

    async def remove_student(self, user_id: int, student_id: str):
        """Удалить студента из выбора"""
        students = await self.get_selected_students(user_id)
        students.pop(student_id, None)
        await self.set_selected_students(user_id, students)

    async def clear_selected_students(self, user_id: int):
        """Очистить выбор студентов для пользователя"""
        try:
            key = self._get_user_key(user_id)
            self.redis.delete(key)
        except Exception as e:
            logger.error(f"Error clearing selected students for user {user_id}: {e}")

    async def set_user_data(self, user_id: int, key: str, data: dict, ttl: int = 3600):
        """Универсальный метод для сохранения данных пользователя"""
        try:
            redis_key = self._get_session_key(user_id, key)
            self.redis.setex(redis_key, ttl, json.dumps(data))
        except Exception as e:
            logger.error(f"Error setting user data for user {user_id}, key {key}: {e}")

    async def get_user_data(self, user_id: int, key: str) -> Optional[dict]:
        """Универсальный метод для получения данных пользователя"""
        try:
            redis_key = self._get_session_key(user_id, key)
            data = self.redis.get(redis_key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Error getting user data for user {user_id}, key {key}: {e}")
            return None