"""
ETL: xlsx (data/raw/) -> нормализация -> Postgres.

Точка входа, которая связывает вместе остальные модули этого пакета:
  config.py     — пути к файлам, подключение к БД, курс валют
  normalize.py  — нормализация кодов проектов, дат, сумм
  extract.py    — чтение xlsx и сборка нормализованных строк
  load.py       — создание схемы и запись данных в Postgres

Делает:
  1. Подключается к БД.
  2. Создаёт таблицы (выполняет sql/create_tables.sql, если их ещё нет).
  3. Читает xlsx из data/raw/, нормализует данные (project_code, даты, суммы).
  4. Приводит бюджеты к единой валюте (RUB) по фиксированному курсу.
  5. Заливает всё в БД (перед загрузкой таблицы очищаются, чтобы
     скрипт можно было запускать повторно).

Аналитические запросы после загрузки — в sql/analysis.sql.

Зависимости: см. requirements.txt в корне проекта
    pip install -r requirements.txt
"""

import sys

import psycopg2

from config import BUDGETS_FILE, DB_CONFIG, DDL_FILE, LANDSCAPE_FILE, SCHEDULE_FILE
from extract import load_budgets, load_landscape, load_schedule
from load import (
    create_tables,
    insert_items,
    insert_payments,
    insert_projects,
    insert_tasks,
    truncate_tables,
)


def main():
    for f in (SCHEDULE_FILE, BUDGETS_FILE, LANDSCAPE_FILE, DDL_FILE):
        if not f.exists():
            sys.exit(f"Не найден файл: {f}")

    print("Читаю и нормализую xlsx...")
    projects, tasks = load_schedule()
    payments = load_budgets()
    items = load_landscape()

    unknown_codes = {c for c, _ in items} - set(projects)
    unknown_codes |= {p[0] for p in payments} - set(projects)
    if unknown_codes:
        sys.exit(f"project_code без соответствия в projects_schedule.xlsx: {sorted(unknown_codes)}")

    print(f"  projects: {len(projects)}")
    print(f"  project_tasks: {len(tasks)}")
    print(f"  project_payments: {len(payments)}")
    print(f"  project_it_items: {len(items)}")

    print(f"Подключаюсь к БД {DB_CONFIG['user']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}...")
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        print("Создаю таблицы (если их ещё нет)...")
        create_tables(conn)

        print("Очищаю таблицы перед загрузкой...")
        truncate_tables(conn)

        print("Загружаю данные...")
        n = insert_projects(conn, projects)
        print(f"  projects: вставлено {n}")
        n = insert_tasks(conn, tasks)
        print(f"  projectst_tasks: вставлено {n}")
        n = insert_payments(conn, payments)
        print(f"  project_payments: вставлено {n}")
        n = insert_items(conn, items)
        print(f"  project_it_items: вставлено {n}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print("Готово.")


if __name__ == "__main__":
    main()
