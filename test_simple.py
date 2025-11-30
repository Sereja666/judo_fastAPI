# test_simple.py
import httpx
import asyncio


async def test_basic():
    """Простой тест доступности Superset"""
    print("🔍 Базовая проверка доступности...")

    # Пробуем разные комбинации
    tests = [
        ("HTTP локальный", "http://localhost:8088/health"),
        ("HTTP docker", "http://172.17.0.1:8088/health"),
        ("HTTPS публичный", "https://superset.srm-1legion.ru/health"),
        ("HTTP публичный", "http://superset.srm-1legion.ru/health"),
    ]

    for name, url in tests:
        print(f"\n🔹 {name}: {url}")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=5.0, follow_redirects=True)
                print(f"   ✅ Статус: {response.status_code}")
                if response.status_code == 200:
                    print("   🎉 РАБОТАЕТ!")
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(test_basic())