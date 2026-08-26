"""
Сборка презентации (.pptx) из готовых графиков и цифр.

Читает PNG из charts/output/ (их кладёт туда charts/main.py) и
раскладывает по слайдам согласно docs/presentation_plan.md. Текст
заголовков и выводов — константы в этом файле: они не считаются, а
формулируются человеком.

Результат — деск-заготовка, а не финальный дизайн: правильные слайды,
графики на местах, цифры и выводы вписаны. Дальше открывается в
PowerPoint и дорабатывается руками.

Запуск (из корня проекта, после etl/main.py и charts/main.py):
    python deck.py

Зависимости: python-pptx (см. requirements.txt).
"""

import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent
CHARTS = ROOT / "charts" / "output"
OUT_FILE = ROOT / "portfolio_audit.pptx"

# 16:9
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

INK = RGBColor(0x0B, 0x0B, 0x0B)
INK_SOFT = RGBColor(0x52, 0x51, 0x4E)
ACCENT = RGBColor(0x2A, 0x78, 0xD6)

MARGIN = Inches(0.6)
TITLE_TOP = Inches(0.45)
BODY_TOP = Inches(1.55)


def _textbox(slide, left, top, width, height, text, size, color=INK, bold=False):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    for i, line in enumerate(text.split("\n")):
        para = p if i == 0 else tf.add_paragraph()
        run = para.add_run()
        run.text = line
        run.font.size = Pt(size)
        run.font.color.rgb = color
        run.font.bold = bold
        run.font.name = "Arial"
    return box


def _title(slide, text):
    _textbox(slide, MARGIN, TITLE_TOP, SLIDE_W - 2 * MARGIN, Inches(0.7),
             text, 30, INK, bold=True)


def _caption(slide, left, top, width, text):
    _textbox(slide, left, top, width, Inches(0.5), text, 12, INK_SOFT)


def _picture(slide, name, left, top, height):
    """Вставляет PNG по высоте, ширину считает по пропорции файла."""
    path = CHARTS / name
    if not path.exists():
        sys.exit(f"Не найден график: {path}\nЗапускали charts/main.py?")
    return slide.shapes.add_picture(str(path), left, top, height=height)


def _blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


# --------------------------------------------------------------- слайды

def slide_1(prs, kpi):
    s = _blank(prs)
    _title(s, "Портфель ИТ-проектов: масштаб и полнота данных")

    col_w = Inches(2.9)
    for i, (value, label) in enumerate(kpi):
        left = MARGIN + Inches(i * 3.05)
        _textbox(s, left, BODY_TOP, col_w, Inches(0.6), value, 26, ACCENT, bold=True)
        _textbox(s, left, BODY_TOP + Inches(0.55), col_w, Inches(0.4), label, 13, INK_SOFT)

    _picture(s, "category_split_donut.png", Inches(4.87), Inches(2.85), Inches(3.7))
    _caption(s, MARGIN, Inches(6.75), Inches(12.1),
             "77 технологических проектов против 23 офисно-коммерческих — "
             "контекст для сравнения на слайде 4.")


def slide_2(prs):
    s = _blank(prs)
    _title(s, "Анализ расписания: где именно теряем время")

    _picture(s, "top5_overrun_bar.png", MARGIN, BODY_TOP, Inches(3.1))
    _picture(s, "stage_benchmark_bar.png", Inches(6.9), BODY_TOP, Inches(2.4))
    _picture(s, "overrun_histogram.png", Inches(6.9), Inches(4.35), Inches(2.2))

    _caption(s, MARGIN, Inches(5.1), Inches(5.6),
             "Топ-5 проектов по срыву дедлайна. Звёздочка — последняя задача "
             "проекта не закрыта, реальный срыв может быть больше.")
    _caption(s, MARGIN, Inches(6.75), Inches(12.1),
             "68 проектов укладываются в 0–3 дня, хвост из 23 проектов даёт срыв "
             "6–19 дней. Проблема сконцентрирована, а не размазана по портфелю.")


def slide_3(prs):
    s = _blank(prs)
    _title(s, "Финансово-ресурсный анализ")

    _picture(s, "currency_donut.png", MARGIN, BODY_TOP, Inches(3.0))
    _picture(s, "top3_pm_budget_bar.png", Inches(4.5), BODY_TOP, Inches(2.6))
    _picture(s, "pm_reliability_scatter.png", Inches(8.9), BODY_TOP, Inches(2.9))

    _caption(s, MARGIN, Inches(5.3), Inches(3.4),
             "96% стоимости — валютные платежи, пересчитанные по условному курсу "
             "из ТЗ. Итог чувствителен к этому допущению.")
    _caption(s, Inches(4.5), Inches(5.3), Inches(3.9),
             "Топ-3 PM по объёму освоенного бюджета.")
    _caption(s, Inches(8.9), Inches(5.3), Inches(3.8),
             "Бюджет и надёжность — разные оси.")

    _textbox(s, MARGIN, Inches(6.6), Inches(12.1), Inches(0.7),
             "Кузнецов В.В. осваивает больше всех бюджета и срывает сроки чаще всех "
             "(56.2% проектов с опозданием). Васильев Н.А., третий по бюджету, — "
             "самый надёжный в портфеле (13.3%).", 13, INK)


def slide_4(prs):
    s = _blank(prs)
    _title(s, "Бизнес-анализ ИТ-ландшафта")
    _picture(s, "category_comparison.png", Inches(1.7), BODY_TOP, Inches(4.4))
    _caption(s, MARGIN, Inches(6.5), Inches(12.1),
             "Проекты разделены по составу закупок: «технологические» — там, где "
             "закупались серверы и системные блоки; «офисно-коммерческие» — только "
             "периферия и расходники.")


def slide_5(prs):
    s = _blank(prs)
    _title(s, "Качество исходных данных")
    _picture(s, "data_quality_bar.png", Inches(2.2), BODY_TOP, Inches(4.3))
    _caption(s, MARGIN, Inches(6.4), Inches(12.1),
             "Все три источника содержат систематические, а не разовые дефекты ввода: "
             "битые коды проектов, суммы текстом, даты-заглушки вместо пустых значений. "
             "Разовых сбоев и дублей в данных нет.")


def slide_6(prs, conclusions):
    s = _blank(prs)
    _title(s, "Выводы и рекомендации")
    top = BODY_TOP
    for head, body in conclusions:
        _textbox(s, MARGIN, top, Inches(12.1), Inches(0.4), head, 17, ACCENT, bold=True)
        _textbox(s, MARGIN, top + Inches(0.42), Inches(12.1), Inches(0.7), body, 13, INK)
        top += Inches(1.28)


# --------------------------------------------------------------- контент

KPI = [
    ("100", "проектов в портфеле"),
    ("12.0 млрд ₽", "общая стоимость"),
    ("120.0 млн ₽", "средний проект"),
    ("98.3%", "задач закрыто"),
]

CONCLUSIONS = [
    ("Сроки под контролем, но есть очаг",
     "68 из 100 проектов укладываются в 0–3 дня от плана. Проблема — в хвосте из 23 "
     "проектов со срывом до 19 дней. Систематически недооценены этапы разработки и "
     "тестирования: закладывать буфер именно на них."),
    ("Оценка портфеля держится на допущении о курсе",
     "96% стоимости — валютные платежи, пересчитанные по фиксированному курсу из ТЗ "
     "(1 USD = 90 ₽, 1 EUR = 100 ₽). Отклонение реального курса на 10% меняет итог на "
     "сотни миллионов рублей. Указывать курс как допущение, а не как факт."),
    ("Объём бюджета не равен надёжности",
     "Лидер по освоенному бюджету — одновременно PM с худшей дисциплиной сроков. "
     "Оценивать руководителей по обеим осям, а не только по объёму."),
    ("Данные нужно чинить на входе, а не на выходе",
     "Все найденные дефекты систематические и локализованы в трёх формах ввода. "
     "Рекомендации: справочник проектов вместо свободного ввода кода, числовое поле "
     "для суммы, пустое состояние для дат вместо заглушек."),
]


def main():
    if not CHARTS.exists():
        sys.exit(f"Нет каталога с графиками: {CHARTS}\nЗапустите сначала charts/main.py")

    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    slide_1(prs, KPI)
    slide_2(prs)
    slide_3(prs)
    slide_4(prs)
    slide_5(prs)
    slide_6(prs, CONCLUSIONS)

    prs.save(OUT_FILE)
    print(f"Готово: {len(prs.slides._sldIdLst)} слайдов -> {OUT_FILE}")


if __name__ == "__main__":
    main()
