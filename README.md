#  Telegram бот на aiogram + веб-приложение на FastAPI

```
Идея такая - создаю свою СРМ на базе Apache Superset, aiogram, FastAPI, postgres.

Тематика - спортивная школа.
Тренера и администраторы используют Telegram как инструмент ввода информации, например отмечают посещаемость учеников, все данные перетекают в Postgres, от туда Superset строит разные дашборды.
FastAPI закрывает тот функцианал недоступный в Superset и неудобный для aiogram. Например создание анкет новых учеников, или редактирование расписание вынесены в отдельное вебприложение.
Для ежедневных задач как списывание занятий и корректировки, используются обычные python скрипты запускающиеся через cron на debian сервере.


```

## Установка

Для установки необходимых зависимостей выполните следующие команды:

```bash
pip install -r requirements.txt
```

где requirements.txt содержит следующие зависимости:

``` requirements
asyncpg-lite~=0.3.1
aiogram~=3.7.0
python-decouple~=3.8
pytz
```

## Использование

Чтобы запустить бота, выполните следующие шаги:

``` bash
pip install -r requirements.txt
```

## Гит
для гит
git pull

## Алембик
alembic revision --autogenerate -m "добавил таблицы со  справками по болезни"
alembic upgrade head


python api_Students_shedule.py

