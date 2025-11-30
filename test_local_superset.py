# test_local_superset.py
import httpx
import asyncio


async def test_local_urls():
    test_urls = [
        "http://localhost:8088",
        "http://host.docker.internal:8088",
        "http://172.17.0.1:8088",
        "http://superset:8088",
        "https://superset.srm-1legion.ru"  # оригинальный
    ]

    print("🔍 Тестируем подключение к Superset...")

    for url in test_urls:
        print(f"\n🔹 Пробуем: {url}")
        try:
            async with httpx.AsyncClient() as client:
                # Короткий таймаут для локальных URL
                timeout = 3.0 if url.startswith('http://') else 10.0

                response = await client.get(f"{url}/api/v1/me", timeout=timeout)
                print(f"   ✅ Статус: {response.status_code}")

                if response.status_code == 200:
                    print("   🎉 РАБОТАЕТ! Используйте этот URL")
                    return url

        except httpx.ConnectError:
            print("   ❌ Ошибка подключения")
        except httpx.TimeoutException:
            print("   ⏰ Таймаут")
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")

    print("\n❌ Ни один URL не сработал")
    return None


if __name__ == "__main__":
    working_url = asyncio.run(test_local_urls())
    if working_url:
        print(f"\n💡 Рекомендуемый URL для config.ini: {working_url}")