# test_local_superset_https.py
import httpx
import asyncio
import ssl


async def test_local_urls_https():
    test_urls = [
        "https://localhost:8088",  # Пробуем HTTPS для локальных
        "https://172.17.0.1:8088",
        "https://superset.srm-1legion.ru"
    ]

    print("🔍 Тестируем HTTPS подключение к Superset...")

    for url in test_urls:
        print(f"\n🔹 Пробуем: {url}")
        try:
            # Для локальных HTTPS может потребоваться отключить проверку SSL
            verify_ssl = not url.startswith('https://localhost') and not url.startswith('https://172.17.0.1')

            async with httpx.AsyncClient(verify=verify_ssl) as client:
                response = await client.get(f"{url}/api/v1/me", timeout=5.0)
                print(f"   ✅ Статус: {response.status_code}")

                if response.status_code == 200:
                    print("   🎉 РАБОТАЕТ! Используйте этот URL")
                    return url
                elif response.status_code in [301, 302, 307, 308]:
                    location = response.headers.get('location', '')
                    print(f"   🔀 Редирект на: {location}")

        except httpx.ConnectError:
            print("   ❌ Ошибка подключения")
        except httpx.TimeoutException:
            print("   ⏰ Таймаут")
        except ssl.SSLError as e:
            print(f"   🔐 SSL ошибка: {e}")
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")

    return None


async def test_with_session_cookie():
    """Тест с реальной сессионной кукой"""
    print("\n🔐 Тестируем с сессионной кукой...")

    # Замените на реальную куку из браузера
    test_cookie = "your_session_cookie_here"

    test_urls = [
        "https://localhost:8088",
        "https://172.17.0.1:8088",
    ]

    for url in test_urls:
        print(f"\n🔹 Пробуем с кукой: {url}")
        try:
            async with httpx.AsyncClient(verify=False) as client:  # Отключаем SSL проверку
                response = await client.get(
                    f"{url}/api/v1/me",
                    cookies={"session": test_cookie},
                    timeout=5.0
                )
                print(f"   ✅ Статус: {response.status_code}")

                if response.status_code == 200:
                    user_data = response.json()
                    print(f"   🎉 АВТОРИЗОВАН! Пользователь: {user_data.get('username')}")
                    return url
                elif response.status_code == 401:
                    print("   ❌ Не авторизован")
                else:
                    print(f"   ⚠️ Неожиданный статус: {response.status_code}")

        except Exception as e:
            print(f"   ❌ Ошибка: {e}")


if __name__ == "__main__":
    print("=== Тест 1: Без куки ===")
    working_url = asyncio.run(test_local_urls_https())

    print("\n=== Тест 2: С кукой ===")
    asyncio.run(test_with_session_cookie())

    if working_url:
        print(f"\n💡 Рекомендуемый URL: {working_url}")