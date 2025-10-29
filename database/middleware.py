# middleware.py
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
import httpx
import json

class SupersetAuthMiddleware:
    def __init__(self, app, superset_base_url: str):
        self.app = app
        self.superset_base_url = superset_base_url

    async def __call__(self, request: Request, call_next):
        # Пропускаем статические файлы и health checks
        if any(request.url.path.startswith(path) for path in ["/static/", "/health", "/debug"]):
            return await call_next(request)

        # Получаем сессионную куку
        session_cookie = request.cookies.get("session")
        
        print(f"🔹 Проверка аутентификации для пути: {request.url.path}")
        print(f"🔹 Сессионная кука: {'есть' if session_cookie else 'нет'}")
        print(f"🔹 Все куки: {dict(request.cookies)}")
        print(f"🔹 Referer: {request.headers.get('referer')}")

        # Если кука есть, проверяем её валидность через Superset API
        if session_cookie:
            try:
                is_valid = await self.validate_superset_session(session_cookie)
                if is_valid:
                    print("✅ Сессия валидна, доступ разрешен")
                    return await call_next(request)
                else:
                    print("❌ Сессия невалидна")
            except Exception as e:
                print(f"❌ Ошибка проверки сессии: {e}")

        # Если куки нет или она невалидна - редирект на логин Superset
        print("🔹 Редирект на страницу логина Superset")
        login_url = f"{self.superset_base_url}/login/?next={request.url}"
        return RedirectResponse(url=login_url)

    async def validate_superset_session(self, session_cookie: str) -> bool:
        """Проверяет валидность сессии через Superset API"""
        try:
            async with httpx.AsyncClient() as client:
                # Создаем куки для запроса
                cookies = {"session": session_cookie}
                
                # Проверяем через endpoint текущего пользователя
                response = await client.get(
                    f"{self.superset_base_url}/api/v1/security/current",
                    cookies=cookies,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    user_data = response.json()
                    print(f"✅ Авторизованный пользователь: {user_data.get('username', 'Unknown')}")
                    return True
                
                print(f"❌ Superset API вернул статус: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка при проверке сессии Superset: {e}")
            return False