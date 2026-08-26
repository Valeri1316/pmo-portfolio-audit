-- ============================================================
-- Схема для данных из projects_schedule.xlsx, projects_budgets.xlsx,
-- it_landscape.xlsx
-- ============================================================

BEGIN;

-- Справочник проектов (project_code + project_name + pm_name
-- согласованы 1:1 во всех трёх файлах после нормализации кода)
CREATE TABLE IF NOT EXISTS projects (
    project_code VARCHAR(20) PRIMARY KEY,
    project_name TEXT NOT NULL,
    pm_name      TEXT NOT NULL
);

-- График задач проекта (из projects_schedule.xlsx)
CREATE TABLE IF NOT EXISTS project_tasks (
    id           BIGSERIAL PRIMARY KEY,
    project_code VARCHAR(20) NOT NULL REFERENCES projects(project_code),
    task_name    TEXT NOT NULL,
    plan_start   DATE NOT NULL,
    plan_end     DATE NOT NULL,
    fact_start   DATE,              -- бывает NULL: задача ещё не начата / не проставлена дата
    fact_end     DATE,
    CHECK (plan_end >= plan_start),
    CHECK (fact_end IS NULL OR fact_start IS NULL OR fact_end >= fact_start)
);

CREATE INDEX IF NOT EXISTS idx_project_tasks_project_code ON project_tasks(project_code);

-- Платежи по проекту (из projects_budgets.xlsx)
-- amount/currency — исходное значение как в файле; amount_rub — приведённое
-- к рублю по фиксированному курсу (1 USD = 90 RUB, 1 EUR = 100 RUB),
-- считается на этапе загрузки в Python.
CREATE TABLE IF NOT EXISTS project_payments (
    id           BIGSERIAL PRIMARY KEY,
    project_code VARCHAR(20) NOT NULL REFERENCES projects(project_code),
    payment_date DATE NOT NULL,
    amount       NUMERIC(14,2) NOT NULL CHECK (amount >= 0),
    currency     VARCHAR(3) NOT NULL CHECK (currency IN ('RUB', 'USD', 'EUR')),
    amount_rub   NUMERIC(14,2) NOT NULL CHECK (amount_rub >= 0)
);

CREATE INDEX IF NOT EXISTS idx_project_payments_project_code ON project_payments(project_code);

-- IT-ландшафт / оборудование, закреплённое за проектом (из it_landscape.xlsx)
CREATE TABLE IF NOT EXISTS project_it_items (
    id           BIGSERIAL PRIMARY KEY,
    project_code VARCHAR(20) NOT NULL REFERENCES projects(project_code),
    item_name    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_project_it_items_project_code ON project_it_items(project_code);

COMMIT;
