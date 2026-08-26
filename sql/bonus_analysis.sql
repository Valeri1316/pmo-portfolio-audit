-- ============================================================
-- Бонусная аналитика поверх нормализованных данных
--
-- Не входит в разделы ТЗ (docs/task_description.md) — самостоятельные
-- запросы, которые расширяют обязательный анализ (sql/analysis.sql).
-- Разбор находок и рекомендаций — docs/findings.md, раздел 2.
-- ============================================================


-- 1. Бенчмарк по типовым этапам проекта.
-- У всех 100 проектов один и тот же набор из 6 задач (см. task_name) —
-- это позволяет сравнить этапы между собой и увидеть, какой из них
-- систематически недооценивается на всём портфеле, а не в отдельном
-- проекте.
SELECT
    task_name,
    COUNT(*) AS n_tasks,
    ROUND(AVG(plan_end - plan_start), 1) AS avg_plan_days,
    ROUND(AVG(fact_end - fact_start)
          FILTER (WHERE fact_start IS NOT NULL AND fact_end IS NOT NULL), 1) AS avg_fact_days,
    ROUND(AVG(fact_end - plan_end)
          FILTER (WHERE fact_end IS NOT NULL), 1)                            AS avg_overrun_days,
    ROUND(100.0 * COUNT(*) FILTER (WHERE fact_end IS NOT NULL AND fact_end > plan_end)
          / COUNT(*) FILTER (WHERE fact_end IS NOT NULL), 1)                 AS pct_late
FROM project_tasks
GROUP BY task_name
ORDER BY avg_overrun_days DESC;


-- 2. Надёжность PM по срокам — не только объём освоенного бюджета
-- (как в разделе ТЗ), а % проектов, сданных с опозданием, и средний
-- срыв. Даёт другой разрез той же роли: кто много осваивает — не
-- всегда тот, кто укладывается в сроки.
-- Использует ту же оговорку, что и запрос 1.2 в analysis.sql: для
-- 4 проектов с незакрытой последней задачей MAX(fact_end) занижает
-- реальный срыв.
WITH project_dates AS (
    SELECT project_code, MAX(plan_end) AS plan_end, MAX(fact_end) AS fact_end
    FROM project_tasks
    GROUP BY project_code
),
pm_projects AS (
    SELECT p.pm_name, p.project_code, pd.fact_end - pd.plan_end AS overrun_days
    FROM projects p
    JOIN project_dates pd USING (project_code)
    WHERE pd.fact_end IS NOT NULL
)
SELECT
    pm_name,
    COUNT(*)                                                    AS projects_delivered,
    ROUND(AVG(overrun_days), 1)                                 AS avg_overrun_days,
    COUNT(*) FILTER (WHERE overrun_days > 0)                    AS late_projects,
    ROUND(100.0 * COUNT(*) FILTER (WHERE overrun_days > 0) / COUNT(*), 1) AS pct_late
FROM pm_projects
GROUP BY pm_name
ORDER BY avg_overrun_days DESC;


-- 3. Валютная структура портфеля.
-- Курс в ТЗ зафиксирован условно (1 USD=90, 1 EUR=100) — эта разбивка
-- показывает, насколько итоговая цифра портфеля вообще зависит от
-- этого допущения.
SELECT
    currency,
    COUNT(*)                                                        AS n_payments,
    SUM(amount_rub)                                                 AS total_rub,
    ROUND(100.0 * SUM(amount_rub) / SUM(SUM(amount_rub)) OVER (), 1) AS pct_of_portfolio
FROM project_payments
GROUP BY currency
ORDER BY total_rub DESC;


-- 4. Полнота выполнения портфеля.
-- % задач с проставленным fact_end — быстрый индикатор "здоровья"
-- данных и прогресса портфеля целиком, а не отдельного проекта.
SELECT
    ROUND(AVG(pct_done), 1)                       AS avg_pct_tasks_done,
    COUNT(*) FILTER (WHERE pct_done < 100)         AS projects_not_fully_closed
FROM (
    SELECT project_code,
           100.0 * COUNT(*) FILTER (WHERE fact_end IS NOT NULL) / COUNT(*) AS pct_done
    FROM project_tasks
    GROUP BY project_code
) t;
