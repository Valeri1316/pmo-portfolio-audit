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
            WITH last_task AS (
                SELECT DISTINCT ON (project_code)
                       project_code, fact_end IS NULL AS still_open
                FROM project_tasks
                ORDER BY project_code, plan_end DESC
            ),
            project_dates AS (
                SELECT project_code, MAX(plan_end) AS plan_end, MAX(fact_end) AS fact_end
                FROM project_tasks GROUP BY project_code
            ),
            pm_projects AS (
                SELECT p.pm_name, p.project_code, pd.fact_end - pd.plan_end AS overrun_days
                FROM projects p
                JOIN project_dates pd USING (project_code)
                JOIN last_task lt USING (project_code)
                WHERE pd.fact_end IS NOT NULL
                  AND NOT lt.still_open
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


def stage_estimate_ratio(conn):
    """Коэффициент факт/план по этапам. Зеркало sql/bonus_analysis.sql, запрос 9."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT task_name,
                   COUNT(*),
                   ROUND(AVG(plan_end - plan_start), 1),
                   ROUND(AVG(fact_end - fact_start), 1),
                   ROUND(AVG((fact_end - fact_start)::numeric
                       / NULLIF(plan_end - plan_start, 0)), 3),
                   ROUND(100.0 * (AVG((fact_end - fact_start)::numeric
                       / NULLIF(plan_end - plan_start, 0)) - 1), 1)
            FROM project_tasks
            WHERE fact_end IS NOT NULL AND fact_start IS NOT NULL
            GROUP BY task_name
            ORDER BY 5 DESC
        """)
        return cur.fetchall()


def buffer_balance(conn):
    """Накопленная задержка, буфер и итоговый срыв. Зеркало запроса 10."""
    with conn.cursor() as cur:
        cur.execute("""
            WITH stage_delay AS (
                SELECT project_code, SUM(fact_end - plan_end) AS accumulated_delay
                FROM project_tasks WHERE fact_end IS NOT NULL
                GROUP BY project_code HAVING COUNT(*) = 6
            ),
            gaps AS (
                SELECT project_code, SUM(gap_days) AS buffer_days, COUNT(*) AS transitions
                FROM (
                    SELECT project_code,
                           LEAD(plan_start) OVER (PARTITION BY project_code ORDER BY plan_start)
                               - plan_end AS gap_days
                    FROM project_tasks
                ) g
                WHERE gap_days IS NOT NULL GROUP BY project_code
            ),
            project_overrun AS (
                SELECT project_code, MAX(fact_end) - MAX(plan_end) AS overrun_days
                FROM project_tasks GROUP BY project_code
                HAVING MAX(fact_end) IS NOT NULL
            )
            SELECT ROUND(AVG(sd.accumulated_delay), 1),
                   ROUND(AVG(g.buffer_days), 1),
                   ROUND(AVG(po.overrun_days), 1),
                   ROUND(AVG(g.buffer_days) / NULLIF(AVG(g.transitions), 0), 1)
            FROM stage_delay sd
            JOIN gaps g             USING (project_code)
            JOIN project_overrun po USING (project_code)
        """)
        row = cur.fetchone()
        return dict(zip(("accumulated", "buffer", "overrun", "gap_per_transition"), row))


def category_estimate_ratio(conn):
    """Коэффициент факт/план в разрезе категорий. Зеркало запроса 11."""
    with conn.cursor() as cur:
        cur.execute("""
            WITH categories AS (
                SELECT p.project_code,
                       CASE WHEN EXISTS (
                           SELECT 1 FROM project_it_items i
                           WHERE i.project_code = p.project_code
                             AND i.item_name IN ('Сервер Dell', 'Системный блок HP')
                       ) THEN 'Технологические' ELSE 'Офисно-коммерческие' END AS category
                FROM projects p
            ),
            task_ratio AS (
                SELECT c.category,
                       (t.fact_end - t.fact_start)::numeric
                           / NULLIF(t.plan_end - t.plan_start, 0) AS ratio
                FROM project_tasks t JOIN categories c USING (project_code)
                WHERE t.fact_end IS NOT NULL AND t.fact_start IS NOT NULL
            ),
            project_overrun AS (
                SELECT c.category, MAX(t.fact_end) - MAX(t.plan_end) AS overrun_days
                                FROM project_tasks t JOIN categories c USING (project_code)
                GROUP BY c.category, t.project_code
                HAVING MAX(t.fact_end) IS NOT NULL
            )
            SELECT r.category,
                   COUNT(*),
                   ROUND(100.0 * (AVG(r.ratio) - 1), 1),
                   (SELECT ROUND(AVG(overrun_days), 2) FROM project_overrun o
                     WHERE o.category = r.category),
                   (SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE overrun_days > 0) / COUNT(*), 1)
                      FROM project_overrun o WHERE o.category = r.category)
            FROM task_ratio r GROUP BY r.category ORDER BY 3 DESC
        """)
        return cur.fetchall()

def top5_overrun_detailed(conn):
    """Топ-5 проектов по абсолютному срыву, с деталями. Зеркало запроса 5."""
    with conn.cursor() as cur:
        cur.execute("""
                    WITH last_task AS (SELECT DISTINCT
                    ON (project_code)
                        project_code, fact_end IS NULL AS still_open
                    FROM project_tasks
                    ORDER BY project_code, plan_end DESC
                        ),
                        project_dates AS (
                    SELECT project_code, MIN (plan_start) AS plan_start, MAX (plan_end) AS plan_end, MAX (fact_end) AS fact_end
                    FROM project_tasks
                    GROUP BY project_code
                        ),
                        project_budget AS (
                    SELECT project_code, SUM (amount_rub) AS budget_rub
                    FROM project_payments
                    GROUP BY project_code
                        )
                    SELECT p.project_code,
                           p.project_name,
                           p.pm_name,
                           pd.fact_end - pd.plan_end                              AS overrun_days,
                           ROUND(100.0 * (pd.fact_end - pd.plan_end)
                                     / NULLIF(pd.plan_end - pd.plan_start, 0), 1) AS overrun_pct,
                           ROUND(pb.budget_rub / 1000000.0, 1)                    AS budget_mln,
                           lt.still_open
                    FROM projects p
                             JOIN project_dates pd USING (project_code)
                             JOIN project_budget pb USING (project_code)
                             JOIN last_task lt USING (project_code)
                    WHERE pd.fact_end IS NOT NULL
                    ORDER BY overrun_days DESC LIMIT 5
                    """)
        return cur.fetchall()

def top5_overrun_relative(conn):
    """Топ-5 проектов по % срыва от плановой длительности. Зеркало запроса 6."""
    with conn.cursor() as cur:
        cur.execute("""
                    WITH project_dates AS (SELECT project_code,
                                                  MIN(plan_start) AS plan_start,
                                                  MAX(plan_end)   AS plan_end,
                                                  MAX(fact_end)   AS fact_end
                                           FROM project_tasks
                                           GROUP BY project_code)
                    SELECT p.project_code,
                           p.project_name,
                           pd.fact_end - pd.plan_end                              AS overrun_days,
                           pd.plan_end - pd.plan_start                            AS plan_days,
                           ROUND(100.0 * (pd.fact_end - pd.plan_end)
                                     / NULLIF(pd.plan_end - pd.plan_start, 0), 1) AS overrun_pct
                    FROM projects p
                             JOIN project_dates pd USING (project_code)
                    WHERE pd.fact_end IS NOT NULL
                    ORDER BY overrun_pct DESC LIMIT 5
                    """)
        return cur.fetchall()

def overrun_cost(conn):
    """Стоимость просрочки: опоздавшие проекты и хвост от 6 дней. Зеркало запроса 7."""
    with conn.cursor() as cur:
        cur.execute("""
                    WITH project_dates AS (SELECT project_code, MAX(fact_end) - MAX(plan_end) AS overrun_days
                                           FROM project_tasks
                                           GROUP BY project_code
                                           HAVING MAX(fact_end) IS NOT NULL),
                         project_budget AS (SELECT project_code, SUM(amount_rub) AS budget_rub
                                            FROM project_payments
                                            GROUP BY project_code),
                         portfolio AS (SELECT SUM(amount_rub) AS total_rub
                                       FROM project_payments)
                    SELECT COUNT(*)                                                                                                                                                            FILTER (WHERE pd.overrun_days > 0) AS late_projects, ROUND(SUM(pb.budget_rub) FILTER (WHERE pd.overrun_days > 0) / 1e9, 2) AS late_bln,
                           ROUND(100.0 * SUM(pb.budget_rub) FILTER (WHERE pd.overrun_days > 0)
                    / (SELECT total_rub FROM portfolio),
                                 1)                                                                                         AS                                                                 late_pct,
                           COUNT(*)                                                                                                                                                            FILTER (WHERE pd.overrun_days >= 6) AS tail_projects, ROUND(SUM(pb.budget_rub) FILTER (WHERE pd.overrun_days >= 6) / 1e9, 2) AS tail_bln,
                           ROUND(100.0 * SUM(pb.budget_rub) FILTER (WHERE pd.overrun_days >= 6)
                    / (SELECT total_rub FROM portfolio), 1) AS                                                                 tail_pct
                    FROM project_dates pd
                             JOIN project_budget pb USING (project_code)
                    """)
        row = cur.fetchone()
        return dict(zip(
            ("late_projects", "late_bln", "late_pct", "tail_projects", "tail_bln", "tail_pct"),
            row,
        ))

def budget_concentration(conn):
    """Концентрация бюджета у топ-3 руководителей. Зеркало запроса 8."""
    with conn.cursor() as cur:
        cur.execute("""
                    WITH pm_budget AS (SELECT p.pm_name, SUM(pp.amount_rub) AS total_budget_rub
                                       FROM project_payments pp
                                                JOIN projects p ON p.project_code = pp.project_code
                                       GROUP BY p.pm_name),
                         portfolio AS (SELECT SUM(amount_rub) AS total_rub
                                       FROM project_payments),
                         top3 AS (SELECT SUM(total_budget_rub) AS top3_rub
                                  FROM (SELECT total_budget_rub
                                        FROM pm_budget
                                        ORDER BY total_budget_rub DESC LIMIT 3) t)
                    SELECT 'Топ-3 руководителя'                                  AS segment,
                           ROUND(top3.top3_rub / 1e9, 2)                         AS bln,
                           ROUND(100.0 * top3.top3_rub / portfolio.total_rub, 1) AS pct
                    FROM top3,
                         portfolio
                    """)
        return cur.fetchall()

def buffer_leak(conn):
    """Утечка буфера по переходам между этапами. Зеркало запроса 12."""
    with conn.cursor() as cur:
        cur.execute("""
                    WITH ordered AS (SELECT project_code,
                                            task_name,
                                            plan_start,
                                            plan_end,
                                            fact_end,
                                            LEAD(plan_start) OVER (PARTITION BY project_code ORDER BY plan_start) AS next_plan_start
                                     FROM project_tasks),
                         transitions AS (SELECT fact_end - plan_end        AS stage_overrun_days,
                                                next_plan_start - plan_end AS gap_days
                                         FROM ordered
                                         WHERE next_plan_start IS NOT NULL
                                           AND fact_end IS NOT NULL)
                    SELECT COUNT(*),
                           COUNT(*) FILTER (WHERE stage_overrun_days > gap_days), ROUND(100.0 * COUNT(*) FILTER (WHERE stage_overrun_days > gap_days)
                    / COUNT(*), 1),
                           ROUND(
                                   AVG(GREATEST(stage_overrun_days - gap_days, 0)) FILTER (WHERE stage_overrun_days > gap_days),
                                   1)
                    FROM transitions
                    """)
        row = cur.fetchone()
        return dict(zip(
            ("n_transitions", "leak_transitions", "leak_pct", "avg_leak_days"),
            row,
        ))