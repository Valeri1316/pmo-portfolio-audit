"""Конфигурация ETL: пути к файлам, подключение к БД, курс валют."""

import os
from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
DDL_FILE = ROOT_DIR / "sql" / "create_tables.sql"

RAW_DIR = ROOT_DIR / "data" / "raw"
SCHEDULE_FILE = RAW_DIR / "projects_schedule.xlsx"
BUDGETS_FILE = RAW_DIR / "projects_budgets.xlsx"
LANDSCAPE_FILE = RAW_DIR / "it_landscape.xlsx"

DB_CONFIG = {
    "host": os.environ.get("PGHOST", "localhost"),
    "port": os.environ.get("PGPORT", "5432"),
    "dbname": os.environ.get("PGDATABASE", "myapp"),
    "user": os.environ.get("PGUSER", "postgres"),
    "password": os.environ.get("PGPASSWORD", "secret"),
}

# Фиксированный курс приведения к рублю (условие ТЗ)
RATES_TO_RUB = {
    "RUB": Decimal("1"),
    "USD": Decimal("90"),
    "EUR": Decimal("100"),
}
