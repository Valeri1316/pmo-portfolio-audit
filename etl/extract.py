"""Чтение xlsx и сборка нормализованных строк, готовых к загрузке в БД."""

import openpyxl

from config import BUDGETS_FILE, LANDSCAPE_FILE, SCHEDULE_FILE
from normalize import (
    normalize_amount,
    normalize_date,
    normalize_optional_date,
    normalize_project_code,
    to_rub,
)


def read_rows(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    header = next(rows)
    return header, list(rows)


def load_schedule():
    """-> (projects: dict[code] = (name, pm_name), tasks: list[tuple])"""
    _, rows = read_rows(SCHEDULE_FILE)

    parsed = []
    for r in rows:
        code_raw, name, pm_name, task_name, plan_start, plan_end, fact_start, fact_end = r
        parsed.append({
            "code": normalize_project_code(code_raw),
            "name": name.strip(),
            "pm_name": pm_name.strip(),
            "task_name": task_name.strip(),
            "plan_start": normalize_date(plan_start),
            "plan_end": normalize_date(plan_end),
            "fact_start": normalize_optional_date(fact_start),
            "fact_end": normalize_optional_date(fact_end),
        })

    _strip_implausible_fact_dates(parsed)

    projects = {}
    tasks = []
    for p in parsed:
        projects.setdefault(p["code"], (p["name"], p["pm_name"]))
        tasks.append((
            p["code"], p["task_name"], p["plan_start"], p["plan_end"],
            p["fact_start"], p["fact_end"],
        ))
    return projects, tasks


# Начать (или закончить) задачу раньше собственного plan_start — это
# нормально и часто встречается в данных (см. start_variance_days в
# sql/analysis.sql): бывает, что команда мобилизуется заранее. Поэтому
# для отсева заглушек НЕЛЬЗЯ считать ошибкой любое опережение плана —
# нужен запас на правдоподобные случаи. В этом файле реальное
# опережение не превышает 2 дней; отклонение на порядки больше (в
# заглушке — 1867-2252 дня, то есть годы) — уже не про "начали
# пораньше", а про технический дефолт источника (1970-01-01,
# 1900-01-01, 0001-01-01 и т.п. — конкретное значение заранее не
# известно и не важно). Год запаса — заведомо щедрый порог для
# отделения одного явления от другого на этих данных.
IMPLAUSIBLE_EARLY_MARGIN_DAYS = 365


def _strip_implausible_fact_dates(parsed_tasks):
    """
    Заменяет на None фактические даты (fact_start/fact_end), которые
    более чем на IMPLAUSIBLE_EARLY_MARGIN_DAYS раньше plan_start ТОЙ ЖЕ
    задачи.

    Сравнение — с собственным plan_start строки (а не глобальным
    минимумом по файлу) и с запасом в год, а не "раньше — уже ошибка":
    так правило не путает технический дефолт источника с обычным
    досрочным стартом. Мутирует parsed_tasks на месте.
    """
    anomalies = []
    for p in parsed_tasks:
        for field in ("fact_start", "fact_end"):
            value = p[field]
            if value is not None and (p["plan_start"] - value).days > IMPLAUSIBLE_EARLY_MARGIN_DAYS:
                anomalies.append((p["code"], p["task_name"], field, value))
                p[field] = None

    if anomalies:
        print(
            f"  [info] {len(anomalies)} значений более чем на "
            f"{IMPLAUSIBLE_EARLY_MARGIN_DAYS} дней раньше plan_start своей "
            f"задачи — похоже на заглушки источника, а не на досрочный "
            f"старт, заменены на NULL:"
        )
        for code, task_name, field, value in anomalies:
            print(f"    {code} / {task_name}: {field}={value.isoformat()}")


def load_budgets():
    """-> list[tuple(project_code, payment_date, amount, currency, amount_rub)]"""
    _, rows = read_rows(BUDGETS_FILE)
    payments = []
    for r in rows:
        code_raw, payment_date, amount_raw, currency = r
        code = normalize_project_code(code_raw)
        currency = str(currency).strip().upper()
        amount = normalize_amount(amount_raw)
        payments.append((
            code,
            normalize_date(payment_date),
            amount,
            currency,
            to_rub(amount, currency),
        ))
    return payments


def load_landscape():
    """-> list[tuple(project_code, item_name)]"""
    _, rows = read_rows(LANDSCAPE_FILE)
    items = []
    for r in rows:
        code_raw, _name, item_name = r
        code = normalize_project_code(code_raw)
        items.append((code, item_name.strip()))
    return items
