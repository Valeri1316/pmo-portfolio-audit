"""Нормализация сырых значений из xlsx: коды проектов, даты, суммы, валюта."""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from config import RATES_TO_RUB

PROJECT_CODE_RE = re.compile(r"^PRJ-?(\d+)$", re.IGNORECASE)
DATE_FORMATS = ("%d.%m.%Y", "%Y-%m-%d", "%Y/%m/%d")


def normalize_project_code(raw):
    """PRJ001 / prj-1 / PRJ-001 -> 'PRJ-001'."""
    code = str(raw).strip().upper()
    m = PROJECT_CODE_RE.match(code)
    if not m:
        raise ValueError(f"неожиданный формат project_code: {raw!r}")
    return f"PRJ-{int(m.group(1)):03d}"


def normalize_date(raw):
    """Приводит дату к datetime.date. Понимает DD.MM.YYYY, YYYY-MM-DD, YYYY/MM/DD."""
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    s = str(raw).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"не удалось распознать дату: {raw!r}")


def normalize_optional_date(raw):
    if raw is None or str(raw).strip() == "":
        return None
    return normalize_date(raw)


def normalize_amount(raw):
    """
    Приводит сумму к Decimal с 2 знаками после запятой.
    Понимает как числа (int/float), так и строки вида '380 675 руб'.
    """
    if isinstance(raw, (int, float)):
        return Decimal(str(raw)).quantize(Decimal("0.01"))

    s = str(raw).strip()
    s = re.sub(r"[^\d,.\-]", "", s)  # выкидываем всё, кроме цифр, ',', '.', '-'
    if not s:
        raise ValueError(f"пустая сумма после очистки: {raw!r}")

    if "," in s and "." in s:
        s = s.replace(",", "")  # запятая — разделитель тысяч
    elif "," in s:
        head, _, tail = s.rpartition(",")
        if len(tail) <= 2:  # запятая как десятичный разделитель
            s = f"{head}.{tail}"
        else:
            s = s.replace(",", "")

    try:
        return Decimal(s).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError(f"не удалось разобрать сумму: {raw!r}") from exc


def to_rub(amount, currency):
    rate = RATES_TO_RUB.get(currency)
    if rate is None:
        raise ValueError(f"неизвестная валюта: {currency!r}")
    return (amount * rate).quantize(Decimal("0.01"))
