"""
Генератор графиков для презентации: Postgres -> charts/output/*.png.

Точка входа, которая связывает вместе остальные модули этого пакета:
  config.py        — пути, подключение к БД, каталог вывода
  style.py          — палитра и общее оформление осей (dataviz skill)
  queries.py         — выборки из БД, зеркало sql/analysis.sql и
                        sql/bonus_analysis.sql
  data_quality.py    — аномалии из сырых xlsx (для слайда о качестве
                        данных — в самой БД они уже устранены)
  plots.py            — рендер каждого графика в SVG

Требует уже загруженную БД (см. README: etl/main.py должен быть запущен
до этого скрипта). Графики — без заголовков/фона, компоновка слайдов и
подписи — в Figma (план — docs/presentation_plan.md).

Зависимости: см. requirements.txt в корне проекта
    pip install -r requirements.txt
"""

import sys

import psycopg2

import data_quality
import plots
import queries
from config import DB_CONFIG, OUTPUT_DIR


def main():
    print(f"Подключаюсь к БД {DB_CONFIG['user']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
    except psycopg2.OperationalError as exc:
        sys.exit(f"Не удалось подключиться к БД (данные уже загружены? см. etl/main.py): {exc}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Строю графики...")
    with conn:
        plots.category_split_donut(queries.category_split(conn), OUTPUT_DIR / "category_split_donut.png")
        plots.top5_overrun_bar(queries.top5_overrun(conn), OUTPUT_DIR / "top5_overrun_bar.png")
        plots.overrun_histogram(queries.overrun_distribution(conn), OUTPUT_DIR / "overrun_histogram.png")
        plots.stage_benchmark_bar(queries.stage_benchmark(conn), OUTPUT_DIR / "stage_benchmark_bar.png")
        plots.top3_pm_budget_bar(queries.top3_pm_budget(conn), OUTPUT_DIR / "top3_pm_budget_bar.png")
        plots.pm_reliability_scatter(queries.pm_reliability(conn), OUTPUT_DIR / "pm_reliability_scatter.png")
        plots.currency_donut(queries.currency_structure(conn), OUTPUT_DIR / "currency_donut.png")
        plots.category_comparison_panels(queries.category_comparison(conn), OUTPUT_DIR / "category_comparison.png")
        plots.buffer_waterfall(queries.buffer_balance(conn), OUTPUT_DIR / "buffer_waterfall.png")

        kpis = queries.kpi_summary(conn)
    conn.close()

    print("Считаю аномалии в сырых xlsx (для слайда о качестве данных)...")
    issues = data_quality.all_issues()
    plots.data_quality_bar(issues, OUTPUT_DIR / "data_quality_bar.png")

    kpi_path = OUTPUT_DIR / "kpi_summary.txt"
    kpi_path.write_text(
        "KPI для слайда 1 (текстовые плашки, не график)\n"
        "===============================================\n"
        f"Проектов в портфеле:            {kpis['projects']}\n"
        f"Общая стоимость портфеля:       {float(kpis['total_portfolio_rub']) / 1e9:.2f} млрд ₽\n"
        f"Средняя стоимость проекта:      {float(kpis['avg_project_rub']) / 1e6:.1f} млн ₽\n"
        f"Задач закрыто в среднем:        {kpis['avg_pct_tasks_done']:.1f}%\n",
        encoding="utf-8",
    )

    png_count = len(list(OUTPUT_DIR.glob("*.png")))
    print(f"Готово: {png_count} PNG + kpi_summary.txt в {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
