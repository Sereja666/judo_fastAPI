import asyncio
import asyncpg

from config import PG_LINK


async def remove_duplicate_student_schedule(db_config: dict):
    """
    Удаляет дубликаты записей в таблице student_schedule
    """
    conn = await asyncpg.connect(**db_config)

    try:
        # 1. Сначала посчитаем сколько дубликатов
        count_result = await conn.fetchval("""
            SELECT COUNT(*) FROM (
                SELECT student, schedule, COUNT(*) 
                FROM public.student_schedule 
                GROUP BY student, schedule 
                HAVING COUNT(*) > 1
            ) AS duplicates
        """)

        if count_result == 0:
            await conn.close()
            return "✅ Дубликатов не найдено"

        # 2. Удаляем дубликаты, оставляя только первую запись для каждой комбинации
        delete_result = await conn.execute("""
            DELETE FROM public.student_schedule 
            WHERE id NOT IN (
                SELECT MIN(id) 
                FROM public.student_schedule 
                GROUP BY student, schedule
            )
        """)

        await conn.close()

        return f"✅ Удалено дубликатов: {count_result} записей"

    except Exception as e:
        await conn.close()
        return f"❌ Ошибка: {str(e)}"


# Функция для просмотра дубликатов перед удалением
async def find_duplicate_student_schedule(db_config: dict):
    """
    Показывает дубликаты перед удалением
    """
    conn = await asyncpg.connect(**db_config)

    duplicates = await conn.fetch("""
        SELECT student, schedule, COUNT(*) as duplicate_count
        FROM public.student_schedule 
        GROUP BY student, schedule 
        HAVING COUNT(*) > 1
        ORDER BY duplicate_count DESC
    """)

    await conn.close()

    if not duplicates:
        return "✅ Дубликатов не найдено"

    result = ["Найдены дубликаты:"]
    for dup in duplicates:
        result.append(f"Студент {dup['student']} + Расписание {dup['schedule']}: {dup['duplicate_count']} записей")

    return "\n".join(result)


# Пример использования
async def main():


    print("🔍 Поиск дубликатов...")
    duplicates_info = await find_duplicate_student_schedule(PG_LINK)
    print(duplicates_info)

    print("\n🗑️ Удаление дубликатов...")
    result = await remove_duplicate_student_schedule(PG_LINK)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())