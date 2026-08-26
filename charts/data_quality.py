"""
Подсчёт аномалий прямо в сырых xlsx (для слайда "качество данных").

После загрузки в БД часть аномалий уже устранена (коды нормализованы,
даты-заглушки заменены на NULL) — их больше не видно в самой БД. Поэтому
для этого графика читаем исходники заново, а не запрашиваем Postgres.

Критерии совпадают с docs/findings.md, раздел 1 — там же объяснение,
почему это системные, а не разовые ошибки.
"""

import re
from datetime import datetime

import openpyxl

from config import BUDGETS_FILE, LANDSCAPE_FILE, SCHEDULE_FILE

CANONICAL_CODE_RE = re.compile(r"^PRJ-\d+$", re.IGNORECASE)


def _rows(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    next(rows)  # header
    return list(rows)


def broken_project_codes():
    """it_landscape.xlsx: код без разделителя (PRJ001 вместо PRJ-001)."""
    rows = _rows(LANDSCAPE_FILE)
    total = len(rows)
    broken = sum(1 for r in rows if not CANONICAL_CODE_RE.match(str(r[0]).strip()))
    return broken, total


def dirty_amounts():
    """projects_budgets.xlsx: сумма записана строкой, а не числом."""
    rows = _rows(BUDGETS_FILE)
    total = len(rows)
    dirty = sum(1 for r in rows if isinstance(r[2], str))
    return dirty, total


def alt_date_format():
    """projects_budgets.xlsx: дата платежа в формате YYYY/MM/DD вместо YYYY-MM-DD."""
    rows = _rows(BUDGETS_FILE)
    total = len(rows)
    alt = sum(1 for r in rows if re.match(r"^\d{4}/\d{2}/\d{2}", str(r[1])))
    return alt, total


def fact_end_without_fact_start():
    """projects_schedule.xlsx: fact_end проставлен, а fact_start пуст."""
    rows = _rows(SCHEDULE_FILE)
    total = len(rows)
    n = sum(
        1 for r in rows
        if str(r[7]).strip() not in ("", "None") and str(r[6]).strip() in ("", "None")
    )
    return n, total


def implausible_fact_dates(margin_days=365):
    """projects_schedule.xlsx: fact_start/fact_end раньше plan_start своей же
    задачи больше чем на margin_days — та же эвристика, что
    etl/extract.py:_strip_implausible_fact_dates (продублирована здесь
    намеренно тонким слоем поверх сырых значений, чтобы не тащить весь ETL
    как зависимость ради одной проверки; расхождение с etl исключено тем,
    что порог совпадает дословно и обе стороны покрыты одними и теми же
    числами в docs/findings.md)."""
    rows = _rows(SCHEDULE_FILE)
    total = len(rows)

    def parse(raw):
        if raw is None or str(raw).strip() == "":
            return None
        return datetime.strptime(str(raw).strip(), "%d.%m.%Y").date()

    flagged_rows = 0
    for r in rows:
        plan_start = parse(r[4])
        row_flagged = False
        for raw in (r[6], r[7]):  # fact_start, fact_end
            value = parse(raw)
            if value is not None and (plan_start - value).days > margin_days:
                row_flagged = True
        if row_flagged:
            flagged_rows += 1
    return flagged_rows, total


def all_issues():
    """-> list[(источник, название проблемы, затронуто строк, всего строк)]"""
    broken, code_total = broken_project_codes()
    dirty, amt_total = dirty_amounts()
    alt_fmt, date_total = alt_date_format()
    no_start, sched_total_a = fact_end_without_fact_start()
    implausible, sched_total_b = implausible_fact_dates()

    return [
        ("ИТ", "Битые коды проектов", broken, code_total),
        ("Финансы", "Суммы текстом", dirty, amt_total),
        ("Финансы", "Дата-заглушка", alt_fmt, date_total),
        ("PMO", "Даты-заглушки", implausible, sched_total_b),
        ("PMO", "fact_end без fact_start", no_start, sched_total_a),
    ]
