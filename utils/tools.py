import asyncio

from db_handler.db_funk import execute_raw_sql


async def add_student_to_schedule(student_name: str, schedule_id: int) -> tuple[bool, str]:
    """
    Асинхронно добавляет студента в расписание по имени

    Args:
        student_name: Имя студента (полное совпадение)
        schedule_id: ID расписания

    Returns:
        Кортеж (успех: bool, сообщение: str)
    """
    try:
        # 1. Находим ID студента
        student_query = f"""
        SELECT id FROM public.student 
        WHERE name like '%{student_name}%';
        """
        student_data = await execute_raw_sql(student_query)
        print(student_data)

        if not student_data:
            return False, f"Студент '{student_name}' не найден"

        student_id = student_data[0]['id']

        # 2. Проверяем дубли
        check_query = f"""
        SELECT 1 FROM public.student_schedule
        WHERE student = {student_id} AND schedule = {schedule_id};
        """
        exists = await execute_raw_sql(check_query)

        if exists:
            return False, "Студент уже в этом расписании"

        # 3. Добавляем запись
        insert_query = f"""
        INSERT INTO public.student_schedule (student, schedule)
        VALUES ({student_id}, {schedule_id});
        """
        await execute_raw_sql(insert_query)

        return True, f"Студент {student_name} добавлен в расписание {schedule_id}"

    except Exception as e:
        return False, f"Ошибка: {str(e)}"

s = """Абатуров М
Аносов В
Дутов К
Завдовьев И
Зверев Д
Сулимов С
Теряев Я
Хрысков Д
Хрысков К
Курылев А
Радченко В
"""
s_list = s.split("\n")
print(s_list)




async def main():
    print("Добавляем студента...")
    for name in s_list:
        result = await add_student_to_schedule(name, 8) #22 23
        print(f"Результат: {result}")

if __name__ == "__main__":
    asyncio.run(main())

