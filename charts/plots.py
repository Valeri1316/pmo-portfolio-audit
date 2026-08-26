"""
Рендер каждого графика из docs/presentation_plan.md в отдельный SVG.

Графики намеренно без заголовков и легенд-по-умолчанию — компоновка и
подписи слайдов делаются в Figma (см. README). Стиль и палитра — style.py.
"""

import math

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from style import CATEGORICAL, INK_MUTED, INK_PRIMARY, INK_SECONDARY, apply_base_style, new_figure, save


def _donut(labels, values, label_fmt, out_path):
    """Общий рендер для донат-чартов (доля категории/валюты).
    label_fmt(label, value, pct) -> подпись внутри графика у каждого сегмента."""
    colors = CATEGORICAL[: len(values)]
    total = sum(values)

    fig, ax = new_figure(figsize=(5, 5))
    wedges, _ = ax.pie(
        values, colors=colors, startangle=90, counterclock=False,
        wedgeprops={"width": 0.4, "edgecolor": "none"},
    )
    for wedge, label, value in zip(wedges, labels, values):
        angle = math.radians((wedge.theta2 + wedge.theta1) / 2)
        x, y = 0.78 * math.cos(angle), 0.78 * math.sin(angle)
        pct = 100 * value / total
        ax.text(x, y, label_fmt(label, value, pct), ha="center", va="center", fontsize=10, color=INK_PRIMARY)
    ax.set_aspect("equal")
    save(fig, out_path)


def category_split_donut(rows, out_path):
    """rows: [(category, n), ...] — из queries.category_split()."""
    labels = [r[0] for r in rows]
    values = [r[1] for r in rows]
    _donut(labels, values, lambda label, value, pct: f"{label}\n{value}", out_path)


def currency_donut(rows, out_path):
    """rows: [(currency, total_rub), ...] — из queries.currency_structure()."""
    labels = [r[0] for r in rows]
    values = [float(r[1]) for r in rows]
    _donut(labels, values, lambda label, value, pct: f"{label}\n{pct:.0f}%", out_path)


def top5_overrun_bar(rows, out_path):
    """rows: [(project_code, overrun_days, caveat), ...] — из queries.top5_overrun(),
    отсортированы по убыванию срыва. caveat=True помечается сноской у бара."""
    rows = list(rows)
    labels = [r[0] for r in rows]
    values = [r[1] for r in rows]
    caveats = [r[2] for r in rows]

    fig, ax = new_figure(figsize=(8, 4.5))
    y_pos = range(len(rows))
    ax.barh(y_pos, values, height=0.6, color=CATEGORICAL[0])
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    apply_base_style(ax, x_grid=True, y_grid=False)
    ax.set_xlabel("Срыв дедлайна, дней", color=INK_SECONDARY, fontsize=9)

    for i, (v, caveat) in enumerate(zip(values, caveats)):
        label = f"{v} дн." + (" *" if caveat else "")
        ax.text(v + max(values) * 0.02, i, label, va="center", fontsize=9, color=INK_PRIMARY)

    if any(caveats):
        ax.text(
            0, -0.9, "* последняя задача проекта ещё не закрыта — реальный срыв может быть больше",
            fontsize=7.5, color=INK_MUTED,
        )
    save(fig, out_path)


def overrun_histogram(overrun_days, out_path):
    """overrun_days: список int — из queries.overrun_distribution()."""
    fig, ax = new_figure(figsize=(7, 4.5))
    ax.hist(
        overrun_days, bins=range(min(overrun_days), max(overrun_days) + 2),
        color=CATEGORICAL[0], edgecolor="none", align="left",
    )
    apply_base_style(ax)
    ax.set_xlabel("Срыв дедлайна, дней (< 0 — досрочно)", color=INK_SECONDARY, fontsize=9)
    ax.set_ylabel("Число проектов", color=INK_SECONDARY, fontsize=9)
    ax.axvline(0, color=INK_MUTED, linewidth=1, linestyle=(0, (3, 3)))
    save(fig, out_path)


def stage_benchmark_bar(rows, out_path):
    """rows: [(task_name, avg_plan_days, avg_fact_days, avg_overrun_days), ...]
    из queries.stage_benchmark(), уже отсортированы по убыванию срыва."""
    rows = list(rows)
    labels = [r[0] for r in rows]
    plan_vals = [float(r[1]) for r in rows]
    fact_vals = [float(r[2]) for r in rows]

    x = range(len(rows))
    width = 0.35

    fig, ax = new_figure(figsize=(9, 5))
    ax.bar([i - width / 2 for i in x], plan_vals, width=width, color=CATEGORICAL[0], label="План")
    ax.bar([i + width / 2 for i in x], fact_vals, width=width, color=CATEGORICAL[1], label="Факт")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=20, ha="right")
    apply_base_style(ax)
    ax.set_ylabel("Средняя длительность, дней", color=INK_SECONDARY, fontsize=9)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK_SECONDARY, loc="upper right")
    save(fig, out_path)


def top3_pm_budget_bar(rows, out_path):
    """rows: [(pm_name, total_budget_rub), ...] из queries.top3_pm_budget()."""
    rows = list(rows)
    labels = [r[0] for r in rows]
    values = [float(r[1]) / 1e6 for r in rows]  # млн ₽

    fig, ax = new_figure(figsize=(6, 4))
    ax.bar(range(len(rows)), values, width=0.5, color=CATEGORICAL[0])
    ax.set_xticks(range(len(rows)))
    ax.set_xticklabels(labels, rotation=10, ha="right")
    apply_base_style(ax)
    ax.set_ylabel("Освоенный бюджет, млн ₽", color=INK_SECONDARY, fontsize=9)
    for i, v in enumerate(values):
        ax.text(i, v, f"{v:,.0f}", ha="center", va="bottom", fontsize=9, color=INK_PRIMARY)
    save(fig, out_path)


def pm_reliability_scatter(rows, out_path):
    """rows: [(pm_name, total_budget_rub, pct_late), ...] из queries.pm_reliability()."""
    rows = list(rows)
    x = [float(r[1]) / 1e6 for r in rows]
    y = [float(r[2]) for r in rows]
    labels = [r[0] for r in rows]

    fig, ax = new_figure(figsize=(7.5, 5.5))
    ax.scatter(x, y, s=80, color=CATEGORICAL[0], zorder=3)
    apply_base_style(ax)
    ax.set_xlabel("Освоенный бюджет, млн ₽", color=INK_SECONDARY, fontsize=9)
    ax.set_ylabel("Проектов с опозданием, %", color=INK_SECONDARY, fontsize=9)
    _place_labels_without_overlap(fig, ax, x, y, labels)
    save(fig, out_path)


# Кандидаты смещения подписи от точки: (dx, dy в points, va, ha).
_LABEL_OFFSETS = [
    (6, 4, "bottom", "left"),
    (6, -12, "top", "left"),
    (-6, 4, "bottom", "right"),
    (-6, -12, "top", "right"),
]


def _place_labels_without_overlap(fig, ax, x, y, labels):
    """Подписывает точки, измеряя реальные пиксельные bbox'ы уже
    отрисованного текста, а не угадывая коллизию по расстоянию в данных
    (см. dataviz skill, marks-and-anatomy.md: "измерить сначала", "не
    громоздить коллидирующие подписи друг на друга")."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    placed_bboxes = []

    for xi, yi, label in zip(x, y, labels):
        for i, (dx, dy, va, ha) in enumerate(_LABEL_OFFSETS):
            text = ax.annotate(
                label, (xi, yi), xytext=(dx, dy), textcoords="offset points",
                fontsize=8.5, color=INK_PRIMARY, va=va, ha=ha,
            )
            fig.canvas.draw()
            bbox = text.get_window_extent(renderer=renderer)
            is_last_candidate = i == len(_LABEL_OFFSETS) - 1
            if is_last_candidate or not any(bbox.overlaps(pb) for pb in placed_bboxes):
                break
            text.remove()
        placed_bboxes.append(bbox)


def category_comparison_panels(rows, out_path):
    """rows: [(category, avg_budget_rub, avg_overrun_days), ...] из
    queries.category_comparison(). Два раздельных subplot'а (бюджет и срыв) —
    у метрик разный масштаб, dual-axis по правилам dataviz-skill не
    используется (см. anti-patterns.md, "никогда не dual-axis")."""
    rows = list(rows)
    labels = [r[0] for r in rows]
    budgets = [float(r[1]) / 1e6 for r in rows]
    overruns = [float(r[2]) for r in rows]
    colors = CATEGORICAL[: len(rows)]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4.5), dpi=150)
    fig.patch.set_alpha(0)
    for ax in (ax1, ax2):
        ax.patch.set_alpha(0)

    ax1.bar(range(len(rows)), budgets, width=0.5, color=colors)
    ax1.set_xticks(range(len(rows)))
    ax1.set_xticklabels(labels, rotation=10, ha="right")
    apply_base_style(ax1)
    ax1.set_ylabel("Средний бюджет, млн ₽", color=INK_SECONDARY, fontsize=9)
    for i, v in enumerate(budgets):
        ax1.text(i, v, f"{v:,.0f}", ha="center", va="bottom", fontsize=9, color=INK_PRIMARY)

    ax2.bar(range(len(rows)), overruns, width=0.5, color=colors)
    ax2.set_xticks(range(len(rows)))
    ax2.set_xticklabels(labels, rotation=10, ha="right")
    apply_base_style(ax2)
    ax2.set_ylabel("Средний срыв, дней", color=INK_SECONDARY, fontsize=9)
    for i, v in enumerate(overruns):
        ax2.text(i, v, f"{v:.1f}", ha="center", va="bottom", fontsize=9, color=INK_PRIMARY)

    save(fig, out_path)


def data_quality_bar(issues, out_path):
    """issues: [(source, label, n_affected, n_total), ...] из
    data_quality.all_issues(). Цвет кодирует источник (PMO/Финансы/ИТ)."""
    issues = list(issues)
    sources = sorted({row[0] for row in issues})
    source_color = {src: CATEGORICAL[i] for i, src in enumerate(sources)}

    labels = [f"{row[1]}\n({row[0]})" for row in issues]
    pct = [100 * row[2] / row[3] for row in issues]
    colors = [source_color[row[0]] for row in issues]

    fig, ax = new_figure(figsize=(9, 5))
    ax.bar(range(len(issues)), pct, width=0.5, color=colors)
    ax.set_xticks(range(len(issues)))
    ax.set_xticklabels(labels, fontsize=8.5)
    apply_base_style(ax)
    ax.set_ylabel("Затронуто строк, %", color=INK_SECONDARY, fontsize=9)
    for i, (p, row) in enumerate(zip(pct, issues)):
        ax.text(i, p, f"{p:.1f}%\n({row[2]}/{row[3]})", ha="center", va="bottom", fontsize=8, color=INK_PRIMARY)

    handles = [Patch(color=source_color[s], label=s) for s in sources]
    ax.legend(handles=handles, frameon=False, fontsize=9, labelcolor=INK_SECONDARY, loc="upper right")
    save(fig, out_path)
