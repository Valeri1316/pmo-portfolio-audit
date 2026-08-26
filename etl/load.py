"""Создание схемы и запись нормализованных данных в Postgres."""

from psycopg2.extras import execute_values

from config import DDL_FILE


def create_tables(conn):
    ddl = DDL_FILE.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()


def truncate_tables(conn):
    with conn.cursor() as cur:
        cur.execute(
            "TRUNCATE project_tasks, project_payments, project_it_items, projects "
            "RESTART IDENTITY CASCADE"
        )
    conn.commit()


def insert_projects(conn, projects):
    rows = [(code, name, pm_name) for code, (name, pm_name) in projects.items()]
    with conn.cursor() as cur:
        execute_values(
            cur,
            "INSERT INTO projects (project_code, project_name, pm_name) VALUES %s",
            rows,
        )
    conn.commit()
    return len(rows)


def insert_tasks(conn, tasks):
    with conn.cursor() as cur:
        execute_values(
            cur,
            "INSERT INTO project_tasks "
            "(project_code, task_name, plan_start, plan_end, fact_start, fact_end) "
            "VALUES %s",
            tasks,
        )
    conn.commit()
    return len(tasks)


def insert_payments(conn, payments):
    with conn.cursor() as cur:
        execute_values(
            cur,
            "INSERT INTO project_payments "
            "(project_code, payment_date, amount, currency, amount_rub) VALUES %s",
            payments,
        )
    conn.commit()
    return len(payments)


def insert_items(conn, items):
    with conn.cursor() as cur:
        execute_values(
            cur,
            "INSERT INTO project_it_items (project_code, item_name) VALUES %s",
            items,
        )
    conn.commit()
    return len(items)
