"""Тема Dark Pearl Glass: палитра, типографика, отступы и глобальные стили.

Все значения собраны здесь, чтобы оформление менялось в одном месте.
Стилистика по ТЗ v0.4: тёмный сине-фиолетовый фон, полупрозрачные
«стеклянные» панели, перламутровые переливы, голубые и сиреневые акценты.

Правила, которым следует тема (по гайду glassmorphism):
* сначала токены, потом компоненты — в виджетах нет «магических» чисел;
* у каждого интерактивного элемента явные состояния: обычное, наведение,
  нажатие, фокус клавиатуры, недоступное;
* контраст текста не ниже WCAG AA (4.5:1) на фоне панели;
* единый ритм отступов и радиусов.
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase

# --- базовые цвета ---------------------------------------------------------
BG_TOP = QColor("#07050F")
BG_MID = QColor("#120C2B")
BG_BOTTOM = QColor("#1A1038")

PANEL_FILL = QColor(255, 255, 255, 14)
PANEL_FILL_HOVER = QColor(255, 255, 255, 24)
PANEL_FILL_ACTIVE = QColor(139, 92, 246, 46)
PANEL_BORDER = QColor(168, 148, 255, 52)
PANEL_BORDER_ACTIVE = QColor(167, 139, 250, 170)

ACCENT = QColor("#8B5CF6")
ACCENT_LIGHT = QColor("#A78BFA")
ACCENT_SOFT = QColor(139, 92, 246, 70)
BLUE = QColor("#60A5FA")
TEAL = QColor("#2DD4BF")
AMBER = QColor("#F59E0B")
ROSE = QColor("#FB7185")

TEXT = QColor("#EDE9FE")
TEXT_DIM = QColor("#A9A3C9")
# было #736D99 — на фоне #120C2B давало контраст 3.93:1, ниже порога AA
TEXT_MUTED = QColor("#8A84B0")

# Кольцо фокуса клавиатуры: заметное, но не кричащее
FOCUS_RING = QColor(167, 139, 250, 210)

# Строковые дубликаты для QSS
C_TEXT = "#EDE9FE"
C_TEXT_DIM = "#A9A3C9"
C_TEXT_MUTED = "#8A84B0"
C_ACCENT = "#8B5CF6"
C_ACCENT_LIGHT = "#A78BFA"
C_FOCUS = "rgba(167, 139, 250, 0.82)"
C_PANEL = "rgba(255, 255, 255, 0.055)"
C_PANEL_HOVER = "rgba(255, 255, 255, 0.09)"
C_BORDER = "rgba(168, 148, 255, 0.22)"
C_BORDER_HOVER = "rgba(167, 139, 250, 0.55)"
C_SURFACE = "#150F2E"

# --- радиусы ---------------------------------------------------------------
RADIUS_PANEL = 18
RADIUS_CARD = 16
RADIUS_BUTTON = 12
RADIUS_CHIP = 8
RADIUS_PILL = 999

# --- стекло по ТЗ ---
GLASS_TINT = QColor(8, 6, 20, 120)        # тёмная подложка стекла
SPECULAR_PEAK = 152                        # блик по верхней кромке (0.6)
BORDER_TOP_ALPHA = 102                     # рамка сверху (0.4)
BORDER_BOTTOM_ALPHA = 14                   # рамка снизу (0.05)
IRIDESCENT_A = QColor("#FFD1FF")           # перламутр: розовый
IRIDESCENT_B = QColor("#B5E3FF")           # голубой
IRIDESCENT_C = QColor("#FFF4D2")           # золотистый
IRIDESCENT_ALPHA = 16
SHADOW_OFFSET = 10
SHADOW_BLUR = 20
MORPH_MS = 460                             # длительность перетекания подложки

# --- ритм отступов (кратно 4) ---------------------------------------------
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24
SPACE_2XL = 32

# --- типографика -----------------------------------------------------------
TYPE_DISPLAY = 26
TYPE_TITLE = 20
TYPE_SECTION = 12
TYPE_BODY = 10
TYPE_LABEL = 9
TYPE_CAPTION = 9
TYPE_BADGE = 8

FONT_FAMILY = "Segoe UI Variable Display"
FONT_FALLBACK = "Segoe UI"


def resolve_font_family() -> str:
    """Возвращает доступное семейство: Variable Display есть только на Win11."""
    families = set(QFontDatabase.families())
    if FONT_FAMILY in families:
        return FONT_FAMILY
    return FONT_FALLBACK


def font(size: int = TYPE_BODY, weight: QFont.Weight = QFont.Weight.Normal,
         letter_spacing: float = 0.0) -> QFont:
    f = QFont(resolve_font_family(), size)
    f.setWeight(weight)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    if letter_spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, letter_spacing)
    return f


# Роли типографики: одинаковые размеры и веса во всех экранах
def display_font() -> QFont:
    """Крупный заголовок экрана."""
    return font(TYPE_TITLE, QFont.Weight.DemiBold, -0.2)


def section_font() -> QFont:
    """Заголовок блока внутри экрана."""
    return font(TYPE_SECTION, QFont.Weight.DemiBold)


def body_font() -> QFont:
    return font(TYPE_BODY)


def body_strong_font() -> QFont:
    return font(TYPE_BODY, QFont.Weight.DemiBold)


def caption_font() -> QFont:
    return font(TYPE_CAPTION, QFont.Weight.Normal)


def label_font() -> QFont:
    return font(TYPE_LABEL, QFont.Weight.Medium)


def app_stylesheet() -> str:
    """Глобальные стили: скроллбары, поля ввода, меню, подсказки, фокус."""
    return f"""
    QWidget {{
        color: {C_TEXT};
        font-family: "{resolve_font_family()}";
    }}
    QToolTip {{
        background-color: #1B1436;
        color: {C_TEXT};
        border: 1px solid {C_BORDER_HOVER};
        border-radius: {RADIUS_CHIP}px;
        padding: 6px 10px;
    }}
    QScrollArea {{ background: transparent; border: none; }}
    QScrollBar:vertical {{
        background: transparent; width: 10px; margin: 4px 2px 4px 0;
    }}
    QScrollBar::handle:vertical {{
        background: rgba(167, 139, 250, 0.34);
        border-radius: 4px; min-height: 36px;
    }}
    QScrollBar::handle:vertical:hover {{ background: rgba(167, 139, 250, 0.6); }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    QScrollBar:horizontal {{
        background: transparent; height: 10px; margin: 0 4px 2px 4px;
    }}
    QScrollBar::handle:horizontal {{
        background: rgba(167, 139, 250, 0.34);
        border-radius: 4px; min-width: 36px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}
    QLineEdit {{
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid {C_BORDER};
        border-radius: 10px;
        padding: 8px 12px;
        selection-background-color: {C_ACCENT};
    }}
    QLineEdit:hover {{ border: 1px solid rgba(167, 139, 250, 0.4); }}
    QLineEdit:focus {{ border: 1px solid {C_FOCUS}; background: rgba(255, 255, 255, 0.07); }}
    QComboBox {{
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid {C_BORDER};
        border-radius: 10px;
        padding: 7px 12px;
    }}
    QComboBox:hover {{ border: 1px solid rgba(167, 139, 250, 0.4); }}
    QComboBox:focus {{ border: 1px solid {C_FOCUS}; }}
    QComboBox QAbstractItemView {{
        background: {C_SURFACE};
        border: 1px solid {C_BORDER_HOVER};
        border-radius: 10px;
        padding: 4px;
        selection-background-color: rgba(139, 92, 246, 0.45);
        outline: none;
    }}
    QCheckBox {{ spacing: 8px; }}
    QCheckBox::indicator {{
        width: 18px; height: 18px; border-radius: 6px;
        border: 1px solid {C_BORDER};
        background: rgba(255, 255, 255, 0.05);
    }}
    QCheckBox::indicator:hover {{ border: 1px solid rgba(167, 139, 250, 0.5); }}
    QCheckBox::indicator:checked {{
        background: {C_ACCENT};
        border: 1px solid {C_ACCENT_LIGHT};
    }}
    QCheckBox::indicator:focus {{ border: 1px solid {C_FOCUS}; }}
    """
