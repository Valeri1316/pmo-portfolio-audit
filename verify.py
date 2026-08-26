"""
Сверка цифр из документации с фактическими расчётами.

Числа в docs/findings.md и docs/presentation_plan.md вписаны текстом —
они не пересчитываются сами при изменении данных или запросов. Этот
скрипт берёт ожидаемые значения (константы ниже, скопированы из
документации) и сравнивает их с тем, что реально считают
charts/queries.py и charts/data_quality.py.

Расхождение означает одно из двух: либо изменились данные, либо
поправили запрос и забыли обновить документацию. Скрипт называет
конкретную метрику, а не просто падает.

Запуск (из корня проекта):
    python verify.py

Часть проверок читает data/raw/ напрямую и работает всегда; часть
требует загруженной БД (см. README, etl/main.py).
"""

import sys
from pathlib import Path

# charts/ — не пакет (нет __init__.py), поэтому кладём его в путь
# импорта, чтобы переиспользовать уже написанные запросы, а не
# дублировать их здесь третий раз.
sys.path.insert(0, str(Path(__file__).resolve().parent / "charts"))

import psycopg2  # noqa: E402

import data_quality  # noqa: E402
import queries  # noqa: E402
from config import DB_CONFIG  # noqa: E402


def pct(part, total):
    return round(100.0 * part / total, 1)


def checks_from_files():
    """Метрики качества данных — считаются из data/raw/, БД не нужна.
    Ожидаемые значения — docs/findings.md, раздел 1."""
    broken, code_total = data_quality.broken_project_codes()
    dirty, amt_total = data_quality.dirty_amounts()
    stub_date, date_total = data_quality.alt_date_format()
    no_start, sched_a = data_quality.fact_end_without_fact_start()
    implausible, sched_b = data_quality.implausible_fact_dates()

    return [
        ("Битые коды, % строк", 4.8, pct(broken, code_total)),
        ("Грязные суммы, % строк", 3.9, pct(dirty, amt_total)),
        ("Дата-заглушка в платежах, % строк", 2.6, pct(stub_date, date_total)),
        ("fact_end без fact_start, % строк", 2.5, pct(no_start, sched_a)),
        ("Даты-заглушки в сроках, % строк", 1.7, pct(implausible, sched_b)),
    ]


def checks_from_db(conn):
    """Метрики портфеля — требуют загруженной БД.
    Ожидаемые значения — docs/findings.md (2.2) и docs/presentation_plan.md."""
    kpi = queries.kpi_summary(conn)
    pm_late = {row[0]: round(float(row[2]), 1) for row in queries.pm_reliability(conn)}

    return [
        ("Проектов в портфеле", 100, kpi["projects"]),
        ("Портфель, млрд ₽", 12.0, round(float(kpi["total_portfolio_rub"]) / 1e9, 1)),
        ("Средний проект, млн ₽", 120.0, round(float(kpi["avg_project_rub"]) / 1e6, 1)),
        ("Задач закрыто, %", 98.3, round(float(kpi["avg_pct_tasks_done"]), 1)),
        ("Кузнецов В.В., % опозданий", 56.2, pm_late["Кузнецов В.В."]),
        ("Соколов Е.П., % опозданий", 30.8, pm_late["Соколов Е.П."]),
        ("Васильев Н.А., % опозданий", 13.3, pm_late["Васильев Н.А."]),
    ]


def report(results):
    """Печатает таблицу и возвращает число расхождений."""
    print(f"  {'метрика':36} {'в докум.':>9} {'факт':>9}")
    mismatches = 0
    for name, expected, actual in results:
        ok = expected == actual
        if not ok:
            mismatches += 1
        print(f"  {name:36} {expected:>9} {actual:>9}  {'ok' if ok else '<-- РАСХОЖДЕНИЕ'}")
    return mismatches


def main():
    results = []

    print("Считаю метрики качества данных из data/raw/...")
    results += checks_from_files()

    print(
        f"Подключаюсь к БД {DB_CONFIG['user']}@{DB_CONFIG['host']}:"
        f"{DB_CONFIG['port']}/{DB_CONFIG['dbname']}..."
    )
    try:
        conn = psycopg2.connect(**DB_CONFIG)
    except psycopg2.OperationalError as exc:
        sys.exit(f"Не удалось подключиться к БД (запускали etl/main.py?): {exc}")
    try:
        results += checks_from_db(conn)
    finally:
        conn.close()

    print()
    mismatches = report(results)
    print()

    if mismatches:
        sys.exit(
            f"Расхождений: {mismatches} из {len(results)}. "
            f"Документация разошлась с расчётами — сверьте docs/ с выводом выше."
        )
    print(f"Проверено метрик: {len(results)}, расхождений нет.")


if __name__ == "__main__":
    main()
