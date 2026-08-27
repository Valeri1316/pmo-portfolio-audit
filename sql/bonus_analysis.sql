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
--
-- Проекты с незакрытой последней задачей исключены (CTE last_task).
-- Причина: у такого проекта MAX(fact_end) берёт дату предпоследней
-- задачи, и проект выглядит сданным досрочно на десятки дней, хотя
-- на деле ещё не сдан. На текущих данных таких 4 (PRJ-045, PRJ-056,
-- PRJ-089, PRJ-098), и без этого фильтра двое PM ошибочно получали
-- отрицательный средний срыв. В остальных метриках эти проекты
-- остаются — там они не искажают результат.
WITH last_task AS (
    SELECT DISTINCT ON (project_code)
           project_code, fact_end IS NULL AS still_open
    FROM project_tasks
    ORDER BY project_code, plan_end DESC
),
project_dates AS (
    SELECT project_code, MAX(plan_end) AS plan_end, MAX(fact_end) AS fact_end
    FROM project_tasks
    GROUP BY project_code
),
pm_projects AS (
    SELECT p.pm_name, p.project_code, pd.fact_end - pd.plan_end AS overrun_days
    FROM projects p
    JOIN project_dates pd USING (project_code)
    JOIN last_task lt USING (project_code)
    WHERE pd.fact_end IS NOT NULL
      AND NOT lt.still_open
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



-- 9. Коэффициент факт/план по этапам — насколько точна оценка длительности.
-- Считается по каждой задаче как отношение фактической длительности
-- к плановой, затем усредняется по этапу. Берутся только задачи, где
-- заполнены обе фактические даты (585 из 600).
--
-- Смысл метрики: 1.0 означает, что оценка точна. Больше единицы — работа
-- систематически занимает дольше, чем закладывали. Если бы проблема была
-- в конкретных этапах, часть значений была бы меньше единицы.
SELECT
    task_name,
    COUNT(*)                                                          AS n_tasks,
    ROUND(AVG(plan_end - plan_start), 1)                              AS avg_plan_days,
    ROUND(AVG(fact_end - fact_start), 1)                              AS avg_fact_days,
    ROUND(AVG((fact_end - fact_start)::numeric
            / NULLIF(plan_end - plan_start, 0)), 3)                   AS ratio_fact_to_plan,
    ROUND(100.0 * (AVG((fact_end - fact_start)::numeric
            / NULLIF(plan_end - plan_start, 0)) - 1), 1)              AS underestimate_pct
FROM project_tasks
WHERE fact_end IS NOT NULL AND fact_start IS NOT NULL
GROUP BY task_name
ORDER BY ratio_fact_to_plan DESC;


-- 10. Буферный баланс проекта: куда деваются накопленные задержки.
--
-- Если сложить срыв всех шести этапов, получается заметно больше, чем
-- итоговый срыв проекта. Разницу гасит буфер, уже заложенный в план:
-- следующий этап стартует не сразу после планового конца предыдущего,
-- между ними всегда есть зазор.
--
-- Три числа этого запроса образуют каскад: накопленная задержка минус
-- буфер даёт фактический срыв.
WITH stage_delay AS (
    SELECT project_code, SUM(fact_end - plan_end) AS accumulated_delay
    FROM project_tasks
    WHERE fact_end IS NOT NULL
    GROUP BY project_code
    HAVING COUNT(*) = 6
),
gaps AS (
    SELECT project_code, SUM(gap_days) AS buffer_days, COUNT(*) AS transitions
    FROM (
        SELECT project_code,
               LEAD(plan_start) OVER (PARTITION BY project_code ORDER BY plan_start)
                   - plan_end AS gap_days
        FROM project_tasks
    ) g
    WHERE gap_days IS NOT NULL
    GROUP BY project_code
),
project_overrun AS (
    SELECT project_code, MAX(fact_end) - MAX(plan_end) AS overrun_days
    FROM project_tasks
    GROUP BY project_code
    HAVING MAX(fact_end) IS NOT NULL
)
SELECT
    ROUND(AVG(sd.accumulated_delay), 1)  AS accumulated_delay_days,
    ROUND(AVG(g.buffer_days), 1)         AS buffer_days,
    ROUND(AVG(po.overrun_days), 1)       AS project_overrun_days,
    ROUND(AVG(g.buffer_days) / NULLIF(AVG(g.transitions), 0), 1) AS gap_per_transition
FROM stage_delay sd
JOIN gaps g            USING (project_code)
JOIN project_overrun po USING (project_code);


-- 11. Тот же коэффициент факт/план, но в разрезе категорий проекта.
--
-- Зазор между этапами в плане одинаковый для обеих категорий, а ошибка
-- оценки разная. Отсюда следует, что единая поправка к срокам —
-- неправильный инструмент: калибровать нужно по типу проекта.
WITH categories AS (
    SELECT
        p.project_code,
        CASE WHEN EXISTS (
            SELECT 1 FROM project_it_items i
            WHERE i.project_code = p.project_code
              AND i.item_name IN ('Сервер Dell', 'Системный блок HP')
        ) THEN 'Технологические' ELSE 'Офисно-коммерческие' END AS category
    FROM projects p
),
task_ratio AS (
    SELECT
        c.category,
        (t.fact_end - t.fact_start)::numeric
            / NULLIF(t.plan_end - t.plan_start, 0) AS ratio
    FROM project_tasks t
    JOIN categories c USING (project_code)
    WHERE t.fact_end IS NOT NULL AND t.fact_start IS NOT NULL
),
project_overrun AS (
    SELECT c.category,
           MAX(t.fact_end) - MAX(t.plan_end) AS overrun_days
    FROM project_tasks t
    JOIN categories c USING (project_code)
    GROUP BY c.category, t.project_code
    HAVING MAX(t.fact_end) IS NOT NULL
)
SELECT
    r.category,
    COUNT(*)                                              AS n_tasks,
    ROUND(AVG(r.ratio), 3)                                AS ratio_fact_to_plan,
    ROUND(100.0 * (AVG(r.ratio) - 1), 1)                  AS underestimate_pct,
    (SELECT ROUND(AVG(overrun_days), 2) FROM project_overrun o
      WHERE o.category = r.category)                      AS avg_project_overrun_days,
    (SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE overrun_days > 0) / COUNT(*), 1)
       FROM project_overrun o WHERE o.category = r.category) AS pct_late
FROM task_ratio r
GROUP BY r.category
ORDER BY ratio_fact_to_plan DESC;



-- 5. Топ-5 проектов по абсолютному срыву в днях, с деталями для слайда.
-- В отличие от запроса 1.2 (там просто список), здесь сразу считается
-- % срыва относительно плановой длительности проекта и его бюджет —
-- это то, что уходит на слайд без дополнительной обработки в Python.
WITH last_task AS (
    SELECT DISTINCT ON (project_code)
           project_code, fact_end IS NULL AS still_open
    FROM project_tasks
    ORDER BY project_code, plan_end DESC
),
project_dates AS (
    SELECT project_code,
           MIN(plan_start) AS plan_start,
           MAX(plan_end)   AS plan_end,
           MAX(fact_end)   AS fact_end
    FROM project_tasks
    GROUP BY project_code
),
project_budget AS (
    SELECT project_code, SUM(amount_rub) AS budget_rub
    FROM project_payments
    GROUP BY project_code
)
SELECT
    p.project_code,
    p.project_name,
    p.pm_name,
    pd.fact_end - pd.plan_end AS overrun_days,
    ROUND(100.0 * (pd.fact_end - pd.plan_end)
        / NULLIF(pd.plan_end - pd.plan_start, 0), 1) AS overrun_pct,
    ROUND(pb.budget_rub / 1000000.0, 1) AS budget_mln,
    lt.still_open
FROM projects p
JOIN project_dates pd  USING (project_code)
JOIN project_budget pb USING (project_code)
JOIN last_task lt      USING (project_code)
WHERE pd.fact_end IS NOT NULL
ORDER BY overrun_days DESC
LIMIT 5;


-- 6. Тот же список, но топ-5 по % срыва от плановой длительности,
-- а не по абсолютным дням. Показывает, что рейтинги не совпадают:
-- "потерял больше всех дней" и "хуже всех держал план" — разные проекты.
WITH project_dates AS (
    SELECT project_code,
           MIN(plan_start) AS plan_start,
           MAX(plan_end)   AS plan_end,
           MAX(fact_end)   AS fact_end
    FROM project_tasks
    GROUP BY project_code
)
SELECT
    p.project_code,
    p.project_name,
    pd.fact_end - pd.plan_end AS overrun_days,
    pd.plan_end - pd.plan_start AS plan_days,
    ROUND(100.0 * (pd.fact_end - pd.plan_end)
        / NULLIF(pd.plan_end - pd.plan_start, 0), 1) AS overrun_pct
FROM projects p
JOIN project_dates pd USING (project_code)
WHERE pd.fact_end IS NOT NULL
ORDER BY overrun_pct DESC
LIMIT 5;


-- 7. Стоимость просрочки: сколько денег лежит в опоздавших проектах
-- и отдельно — в "хвосте" (срыв от 6 дней и больше).
WITH project_dates AS (
    SELECT project_code, MAX(fact_end) - MAX(plan_end) AS overrun_days
    FROM project_tasks
    GROUP BY project_code
    HAVING MAX(fact_end) IS NOT NULL
),
project_budget AS (
    SELECT project_code, SUM(amount_rub) AS budget_rub
    FROM project_payments
    GROUP BY project_code
),
portfolio AS (
    SELECT SUM(amount_rub) AS total_rub FROM project_payments
)
SELECT
    COUNT(*) FILTER (WHERE pd.overrun_days > 0) AS late_projects,
    ROUND(SUM(pb.budget_rub) FILTER (WHERE pd.overrun_days > 0) / 1e9, 2) AS late_bln,
    ROUND(100.0 * SUM(pb.budget_rub) FILTER (WHERE pd.overrun_days > 0)
        / (SELECT total_rub FROM portfolio), 1) AS late_pct,
    COUNT(*) FILTER (WHERE pd.overrun_days >= 6) AS tail_projects,
    ROUND(SUM(pb.budget_rub) FILTER (WHERE pd.overrun_days >= 6) / 1e9, 2) AS tail_bln,
    ROUND(100.0 * SUM(pb.budget_rub) FILTER (WHERE pd.overrun_days >= 6)
        / (SELECT total_rub FROM portfolio), 1) AS tail_pct
FROM project_dates pd
JOIN project_budget pb USING (project_code);


-- 8. Концентрация бюджета у топ-3 руководителей по объёму освоенных денег.
WITH pm_budget AS (
    SELECT p.pm_name, SUM(pp.amount_rub) AS total_budget_rub
    FROM project_payments pp
    JOIN projects p ON p.project_code = pp.project_code
    GROUP BY p.pm_name
),
portfolio AS (
    SELECT SUM(amount_rub) AS total_rub FROM project_payments
),
top3 AS (
    SELECT SUM(total_budget_rub) AS top3_rub
    FROM (SELECT total_budget_rub FROM pm_budget ORDER BY total_budget_rub DESC LIMIT 3) t
)
SELECT
    'Топ-3 руководителя' AS segment,
    ROUND(top3.top3_rub / 1e9, 2) AS bln,
    ROUND(100.0 * top3.top3_rub / portfolio.total_rub, 1) AS pct
FROM top3, portfolio;