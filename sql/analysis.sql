-- ============================================================
-- 1. АНАЛИЗ РАСПИСАНИЯ
-- ============================================================

-- 1.1 Плановая и фактическая длительность каждой задачи.
-- fact_duration_days и task_overrun_days считаются только если задача
-- уже завершена (fact_end задан) — для незавершённых задач это NULL,
-- а не "0 дней".
SELECT
    project_code,
    task_name,
    plan_start,
    plan_end,
    (plan_end - plan_start)                       AS plan_duration_days,
    fact_start,
    fact_end,
    CASE WHEN fact_start IS NOT NULL AND fact_end IS NOT NULL
         THEN fact_end - fact_start END            AS fact_duration_days,
    CASE WHEN fact_end IS NOT NULL
         THEN fact_end - plan_end END               AS task_overrun_days   -- >0 — просрочка, <0 — досрочно
FROM project_tasks
ORDER BY project_code, plan_start;


-- 1.2 Топ-5 проектов с максимальным срывом дедлайна.
-- Срыв = факт.дата конца проекта минус план.дата конца проекта, где
-- "конец проекта" = дата конца последней по плану/факту задачи (MAX).
--
-- Оговорка: у 4 проектов (см. запрос 1.3.b) последняя по плану задача
-- ещё не имеет fact_end, хотя более ранние задачи того же проекта уже
-- завершены. MAX(fact_end) в этом случае "не замечает" отсутствующую
-- дату и подставляет дату предыдущей завершённой задачи — фактический
-- срыв по такому проекту, вероятно, ещё больше, чем показывает запрос.
-- Такие проекты стоит помечать на презентации отдельно, а не считать
-- цифру окончательной.
WITH project_dates AS (
    SELECT
        project_code,
        MAX(plan_end) AS plan_project_end,
        MAX(fact_end) AS fact_project_end
    FROM project_tasks
    GROUP BY project_code
)
SELECT
    project_code,
    plan_project_end,
    fact_project_end,
    fact_project_end - plan_project_end AS overrun_days
FROM project_dates
WHERE fact_project_end IS NOT NULL
ORDER BY overrun_days DESC
LIMIT 5;


-- 1.3 Логические ошибки ведения плана.

-- 1.3.a Задача помечена завершённой (fact_end задан), но не имеет даты
-- начала (fact_start отсутствует) — по факту нельзя закончить то, что
-- не начиналось. На текущих данных находит 15 задач.
SELECT
    project_code,
    task_name,
    plan_start,
    plan_end,
    fact_start,
    fact_end
FROM project_tasks
WHERE fact_end IS NOT NULL
  AND fact_start IS NULL
ORDER BY project_code;

-- 1.3.b Нарушение последовательности выполнения: задача ещё не
-- завершена (fact_end IS NULL), а другая задача того же проекта,
-- запланированная позже (более поздний plan_start), уже завершена.
-- Это невозможно при последовательном ведении проекта и указывает на
-- ошибку в данных/процессе. Проверка через EXISTS, а не через
-- "соседнюю по списку задачу" — находит нарушение с любой более
-- поздней задачей, а не только с ближайшей следующей.
--
-- На текущих данных находит 6 задач в 6 проектах. Всего в
-- project_tasks было 10 строк с заглушками фактических дат
-- (см. _strip_implausible_fact_dates в etl/extract.py), из них ровно эти 6 —
-- случаи, где "недоделанная" задача идёт не последней в проекте (и
-- значит, налицо нарушение порядка). Оставшиеся 4 заглушки пришлись на
-- Финальный релиз — последнюю задачу проекта: там сравнивать не с чем
-- (более поздней задачи просто нет), это не "нарушение порядка", а
-- проект, который на момент выгрузки данных ещё не завершён. Именно
-- эти 4 проекта и есть оговорка к запросу 1.2 — по ним MAX(fact_end)
-- незаметно берёт дату предпоследней задачи вместо настоящей даты
-- завершения (которой пока попросту нет).
SELECT
    t1.project_code,
    t1.task_name  AS unfinished_task,
    t1.plan_start AS unfinished_plan_start
FROM project_tasks t1
WHERE t1.fact_end IS NULL
  AND EXISTS (
      SELECT 1
      FROM project_tasks t2
      WHERE t2.project_code = t1.project_code
        AND t2.plan_start > t1.plan_start
        AND t2.fact_end IS NOT NULL
  )
ORDER BY t1.project_code;


-- ============================================================
-- 2. ФИНАНСОВО-РЕСУРСНЫЙ АНАЛИЗ
-- ============================================================

-- 2.1 Общая стоимость портфеля и средняя стоимость одного проекта.
-- amount_rub уже приведён к рублю на этапе загрузки (etl/main.py),
-- здесь конвертация валют не нужна.
SELECT
    SUM(amount_rub)                                       AS total_portfolio_rub,
    SUM(amount_rub) / COUNT(DISTINCT project_code)         AS avg_project_cost_rub
FROM project_payments;


-- 2.2 Топ-3 PM по объёму освоенного бюджета (сумма всех платежей по
-- проектам, где данный человек — руководитель).
SELECT
    p.pm_name,
    SUM(pp.amount_rub) AS total_budget_rub
FROM project_payments pp
JOIN projects p ON p.project_code = pp.project_code
GROUP BY p.pm_name
ORDER BY total_budget_rub DESC
LIMIT 3;


-- ============================================================
-- 3. БИЗНЕС-АНАЛИЗ ИТ-ЛАНДШАФТА
-- ============================================================

-- 3.1 Категоризация проектов на "Технологические" и "Офисно-
-- коммерческие" + сравнение среднего бюджета и средней задержки.
--
-- По ТЗ решающие признаки: "Технологические" — где закупались Серверы
-- и Системные блоки; "Офисно-коммерческие" — где фигурируют только
-- наушники, клавиатуры, бублики и кофе. "Монитор Asus" в ТЗ не
-- упомянут; проверка показала, что он встречается в обеих группах
-- примерно пропорционально (42 из 77 "технологических" проектов и 15
-- из 23 "офисно-коммерческих") и не сопровождается в "офисных"
-- проектах никакими наименованиями, кроме описанных в ТЗ — то есть не
-- является различающим признаком, поэтому в классификации не
-- участвует и просто присутствует в обеих группах как общий предмет.
WITH categories AS (
    SELECT
        project_code,
        CASE
            WHEN BOOL_OR(item_name IN ('Сервер Dell', 'Системный блок HP'))
                THEN 'Технологические'
            ELSE 'Офисно-коммерческие'
        END AS category
    FROM project_it_items
    GROUP BY project_code
),
budgets AS (
    SELECT project_code, SUM(amount_rub) AS project_budget
    FROM project_payments
    GROUP BY project_code
),
overruns AS (
    SELECT project_code, MAX(fact_end) - MAX(plan_end) AS overrun_days
    FROM project_tasks
    GROUP BY project_code
    HAVING MAX(fact_end) IS NOT NULL
)
SELECT
    c.category,
    COUNT(DISTINCT c.project_code) AS project_count,
    AVG(b.project_budget)          AS avg_budget_rub,
    AVG(o.overrun_days)            AS avg_overrun_days
FROM categories c
JOIN budgets b ON b.project_code = c.project_code
LEFT JOIN overruns o ON o.project_code = c.project_code
GROUP BY c.category;
