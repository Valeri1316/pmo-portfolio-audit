"""
Единый визуальный стиль для всех графиков (палитра и оформление осей).

Палитра и правила — из skill'а dataviz (references/palette.md,
references/marks-and-anatomy.md): фиксированный порядок категориальных
цветов (никогда не переставлять/не подбирать на глаз — порядок уже
провалидирован на цветовую слепоту), текст всегда в "ink"-тонах, а не в
цвете серии, разряженные (recessive) сетка и оси.

Графики рендерятся БЕЗ заголовков и БЕЗ фона (прозрачный SVG) — заголовки,
подписи слайдов и итоговое оформление добавляются в Figma; так один и тот
же набор графиков не тянет за собой чужой шрифт/цвет поверх фигмовского.
"""

import matplotlib

matplotlib.use("Agg")  # headless: только сохраняем файлы, окно не нужно;
# также даёт предсказуемый renderer для измерения bbox'ов подписей (plots.py)
import matplotlib.pyplot as plt

# Категориальная палитра, фиксированный порядок (dataviz skill, palette.md).
# Использовать по номеру слота, никогда не переставлять и не выбирать частично.
CATEGORICAL = [
    "#2a78d6",  # 1 blue
    "#eb6834",  # 2 orange
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 yellow
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 green
    "#4a3aa7",  # 7 violet
    "#e34948",  # 8 red
]

INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

FONT_FAMILY = "sans-serif"


def new_figure(figsize=(8, 5)):
    fig, ax = plt.subplots(figsize=figsize, dpi=150)
    fig.patch.set_alpha(0)
    ax.patch.set_alpha(0)
    return fig, ax


def apply_base_style(ax, *, x_grid=False, y_grid=True):
    """Общее оформление осей: убрать лишние рамки, разрядить сетку и тики."""
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.spines["bottom"].set_linewidth(1)

    ax.tick_params(colors=INK_MUTED, labelsize=9, length=0)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_color(INK_SECONDARY)
        label.set_fontfamily(FONT_FAMILY)

    if y_grid:
        ax.yaxis.grid(True, color=GRIDLINE, linewidth=1)
        ax.set_axisbelow(True)
    if x_grid:
        ax.xaxis.grid(True, color=GRIDLINE, linewidth=1)
        ax.set_axisbelow(True)


def save(fig, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, transparent=True, dpi=200)
    plt.close(fig)
