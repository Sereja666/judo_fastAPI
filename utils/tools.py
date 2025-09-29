import asyncio

from sqlalchemy.dialects.postgresql import asyncpg

from config import settings
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
        SELECT id FROM big_db.student 
        WHERE name like '%{student_name}%';
        """
        student_data = await execute_raw_sql(student_query)
        if not student_data:
            return False, f"Студент '{student_name}' не найден"

        student_id = student_data[0]['id']
        # 2. Проверяем дубли
        check_query = f"""
        SELECT 1 FROM big_db.student_schedule
        WHERE student = {student_id} AND schedule = {schedule_id};
        """
        exists = await execute_raw_sql(check_query)
        if len(exists) != 0:
            print("Студент уже в этом расписании")
            return False, "Студент уже в этом расписании"

        # 3. Добавляем запись
        print("  # 3. Добавляем запись")
        insert_query = f"""
        INSERT INTO big_db.student_schedule (student, schedule)
        VALUES ({student_id}, {schedule_id});
        """

        await execute_raw_sql(insert_query)

        return True, f"Студент {student_name} добавлен в расписание {schedule_id}"

    except Exception as e:
        return False, f"Ошибка: {str(e)}"


a1 = '''121. 🟦Эприков С. 2009
122. 🟦Тибилашвили К. 2010
123. 🟦Гончарова К. 2010
124. 🟦Екатеринчев А. 2010
125. 🟦Архипов В. 2013
126. 🟦Уварова А. 2012
127. 🟦Кузнецова Е. 2012
128. 🟦Маслов Е. 2012
129. 🟦Килин М. 2012
130. 🟦Козлов И. 2010
131. 🟦Давидова Е. 2012
132. 🟦Гаркуша К. 2011
133. 🟩Бочаров С. 2014
134. 🟧Шатохин Р. 2013
135. 🟧Солончев Р. 2011
136. 🟧Варшанидзе А. 2010
137. 🟧Цыганеш Г. 2013
142. 🟨Капустин 2008
143. ⬜Березовская К. 2008
144. ⬜Ересько Л. 2009
145. ⬜Антоненко А. 2009
146. 🟦Гайдуков Д. 2010
147. ⬜Пестерев Е. 2010
148. 🟧Емельянов Б. 2013
149. 🟦Федоров М. 2009
150. 🟦Пархоменко А. 2010
151. 🟦Анкудинов И. 2011
152. 🟦Ханчукаев Р. 2012
153. 🟦Михайлова С. 2012
154. 🟩Пономаренко В. 2014
155. 🟧Исаханян С. 2010
156. 🟨Русанов Р. 2012
157. ⬜Саенко В. 2009
158. ⬜Щаблевский М. 2007
159. 🟨Саргсян Р. 2007
160. ⬜Малый Б. 2014
161. 🟨Никулина Е. 2011'''

a = """Гусейнов Субхан
Гусейнов Сулейман
Чернышев К
Чернышев Д
"""
s_list = []


# for name in a1.split('\n'):
#     s_list.append(name.split(' ')[1].replace('⬜', '').replace('🟨', '').replace('🟧', '').replace('🟩', '').replace('🟦', ''))

for name in a.split('\n'):
    s_list.append(name)
print(s_list)




async def main():


    for name in s_list:
        print(f"Добавляем студента...{name}")
        result = await add_student_to_schedule(name, 20) #32 33
        # result = await add_new_student(name)  # 22 23

        print(f"Результат: {result}")

if __name__ == "__main__":
    asyncio.run(main())

