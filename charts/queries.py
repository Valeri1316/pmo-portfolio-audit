"""
Выборки данных из Postgres для графиков.

Каждый запрос — прямое зеркало соответствующего запроса из
sql/analysis.sql / sql/bonus_analysis.sql (см. комментарий у каждой
функции), просто оформленное как параметризуемая функция, а не как
самостоятельный .sql-файл — здесь их проще переиспользовать между
графиками и не пересчитывать одно и то же дважды.
"""


def category_split(conn):
    """Число проектов в категориях 'Технологические'/'Офисно-коммерческие'.
    Зеркало categories CTE из sql/analysis.sql, 3.1."""
    with conn.cursor() as cur:
        cur.execute("""
            WITH categories AS (
                SELECT project_code,
                       CASE WHEN BOOL_OR(item_name IN ('Сервер Dell', 'Системный блок HP'))
                            THEN 'Технологические' ELSE 'Офисно-коммерческие' END AS category
                FROM project_it_items
                GROUP BY project_code
            )
            SELECT category, COUNT(*) FROM categories GROUP BY category ORDER BY category
        """)
        return cur.fetchall()


def top5_overrun(conn):
    """Топ-5 проектов по срыву дедлайна + пометка 'caveat', если последняя по
    плану задача проекта ещё не закрыта (fact_end IS NULL) — тот же случай,
    что оговорка в sql/analysis.sql, 1.2. Пометка вычисляется по данным, а не
    по списку кодов — если в других данных таких проектов не будет, каждая
    строка результата просто придёт с caveat=False."""
    with conn.cursor() as cur:
        cur.execute("""
            WITH last_task AS (
                SELECT DISTINCT ON (project_code)
                       project_code, fact_end IS NULL AS still_open
                FROM project_tasks
                ORDER BY project_code, plan_end DESC
            ),
            project_dates AS (
                SELECT project_code,
                       MAX(plan_end) AS plan_project_end,
                       MAX(fact_end) AS fact_project_end
                FROM project_tasks
                GROUP BY project_code
            )
            SELECT pd.project_code,
                   pd.fact_project_end - pd.plan_project_end AS overrun_days,
                   lt.still_open AS caveat
            FROM project_dates pd
            JOIN last_task lt USING (project_code)
            WHERE pd.fact_project_end IS NOT NULL
            ORDER BY overrun_days DESC
            LIMIT 5
        """)
        return cur.fetchall()


def overrun_distribution(conn):
    """Срыв (в днях) по каждому из проектов, у которых он вообще посчитан
    (fact_project_end IS NOT NULL) — сырые значения для гистограммы, бинуем
    уже в matplotlib, а не в SQL, чтобы не терять точность."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT MAX(fact_end) - MAX(plan_end) AS overrun_days
            FROM project_tasks
            GROUP BY project_code
            HAVING MAX(fact_end) IS NOT NULL
        """)
        return [row[0] for row in cur.fetchall()]


def stage_benchmark(conn):
    """Средняя плановая/фактическая длительность и срыв по каждому из 6
    типовых этапов проекта. Зеркало sql/bonus_analysis.sql, запрос 1."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                task_name,
                AVG(plan_end - plan_start) AS avg_plan_days,
                AVG(fact_end - fact_start)
                    FILTER (WHERE fact_start IS NOT NULL AND fact_end IS NOT NULL) AS avg_fact_days,
                AVG(fact_end - plan_end) FILTER (WHERE fact_end IS NOT NULL) AS avg_overrun_days
            FROM project_tasks
            GROUP BY task_name
            ORDER BY avg_overrun_days DESC
        """)
        return cur.fetchall()


def top3_pm_budget(conn):
    """Топ-3 PM по объёму освоенного бюджета. Зеркало sql/analysis.sql, 2.2."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT p.pm_name, SUM(pp.amount_rub) AS total_budget_rub
            FROM project_payments pp
            JOIN projects p ON p.project_code = pp.project_code
            GROUP BY p.pm_name
            ORDER BY total_budget_rub DESC
            LIMIT 3
        """)
        return cur.fetchall()


def pm_reliability(conn):
    """Бюджет и надёжность по срокам для каждого PM. Зеркало
    sql/bonus_analysis.sql, запрос 2."""
    with conn.cursor() as cur:
        cur.execute("""
            WITH project_dates AS (
                SELECT project_code, MAX(plan_end) AS plan_end, MAX(fact_end) AS fact_end
                FROM project_tasks GROUP BY project_code
            ),
            pm_projects AS (
                SELECT p.pm_name, p.project_code, pd.fact_end - pd.plan_end AS overrun_days
                FROM projects p
                JOIN project_dates pd USING (project_code)
                WHERE pd.fact_end IS NOT NULL
            ),
            pm_budget AS (
                SELECT p.pm_name, SUM(pp.amount_rub) AS total_budget_rub
                FROM project_payments pp
                JOIN projects p ON p.project_code = pp.project_code
                GROUP BY p.pm_name
            )
            SELECT
                pp.pm_name,
                pb.total_budget_rub,
                100.0 * COUNT(*) FILTER (WHERE pp.overrun_days > 0) / COUNT(*) AS pct_late
            FROM pm_projects pp
            JOIN pm_budget pb USING (pm_name)
            GROUP BY pp.pm_name, pb.total_budget_rub
            ORDER BY pb.total_budget_rub DESC
        """)
        return cur.fetchall()


def currency_structure(conn):
    """Доля каждой валюты в итоговой стоимости портфеля (в рублях). Зеркало
    sql/bonus_analysis.sql, запрос 3."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT currency, SUM(amount_rub) AS total_rub
            FROM project_payments
            GROUP BY currency
            ORDER BY total_rub DESC
        """)
        return cur.fetchall()


def category_comparison(conn):
    """Средний бюджет и средний срыв по категориям 'Технологические' /
    'Офисно-коммерческие'. Зеркало sql/analysis.sql, 3.1."""
    with conn.cursor() as cur:
        cur.execute("""
            WITH categories AS (
                SELECT project_code,
                       CASE WHEN BOOL_OR(item_name IN ('Сервер Dell', 'Системный блок HP'))
                            THEN 'Технологические' ELSE 'Офисно-коммерческие' END AS category
                FROM project_it_items
                GROUP BY project_code
            ),
            budgets AS (
                SELECT project_code, SUM(amount_rub) AS project_budget
                FROM project_payments GROUP BY project_code
            ),
            overruns AS (
                SELECT project_code, MAX(fact_end) - MAX(plan_end) AS overrun_days
                FROM project_tasks GROUP BY project_code
                HAVING MAX(fact_end) IS NOT NULL
            )
            SELECT c.category, AVG(b.project_budget) AS avg_budget_rub, AVG(o.overrun_days) AS avg_overrun_days
            FROM categories c
            JOIN budgets b ON b.project_code = c.project_code
            LEFT JOIN overruns o ON o.project_code = c.project_code
            GROUP BY c.category
            ORDER BY c.category
        """)
        return cur.fetchall()


def kpi_summary(conn):
    """Headline-цифры для KPI-плашек (слайд 1) — текстом, не графиком."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM projects")
        n_projects = cur.fetchone()[0]

        cur.execute("SELECT SUM(amount_rub), SUM(amount_rub) / COUNT(DISTINCT project_code) FROM project_payments")
        total_rub, avg_project_rub = cur.fetchone()

        cur.execute("""
            SELECT AVG(pct_done) FROM (
                SELECT 100.0 * COUNT(*) FILTER (WHERE fact_end IS NOT NULL) / COUNT(*) AS pct_done
                FROM project_tasks GROUP BY project_code
            ) t
        """)
        avg_pct_done = cur.fetchone()[0]

    return {
        "projects": n_projects,
        "total_portfolio_rub": total_rub,
        "avg_project_rub": avg_project_rub,
        "avg_pct_tasks_done": avg_pct_done,
    }
