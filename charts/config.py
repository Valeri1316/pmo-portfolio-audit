"""Конфигурация генератора графиков: пути, подключение к БД, каталог вывода."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

RAW_DIR = ROOT_DIR / "data" / "raw"
SCHEDULE_FILE = RAW_DIR / "projects_schedule.xlsx"
BUDGETS_FILE = RAW_DIR / "projects_budgets.xlsx"
LANDSCAPE_FILE = RAW_DIR / "it_landscape.xlsx"

OUTPUT_DIR = BASE_DIR / "output"

# Тот же контур подключения, что и etl/config.py (тот же Postgres,
# заполненный этим же etl-пайплайном) — не импортируется из etl напрямую,
# т.к. это самостоятельный, независимо запускаемый инструмент со своим
# набором зависимостей (matplotlib), а не часть ETL-пакета.
DB_CONFIG = {
    "host": os.environ.get("PGHOST", "localhost"),
    "port": os.environ.get("PGPORT", "5432"),
    "dbname": os.environ.get("PGDATABASE", "myapp"),
    "user": os.environ.get("PGUSER", "postgres"),
    "password": os.environ.get("PGPASSWORD", "secret"),
}
