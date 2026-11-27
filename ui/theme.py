"""Тема Dark Pearl Glass: палитра, шрифты и глобальные стили.

Все цвета собраны здесь, чтобы оформление менялось в одном месте.
Стилистика по ТЗ v0.4: тёмный сине-фиолетовый фон, полупрозрачные
«стеклянные» панели, перламутровые переливы, голубые и сиреневые акценты.
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
TEXT_MUTED = QColor("#736D99")

# Строковые дубликаты для QSS
C_TEXT = "#EDE9FE"
C_TEXT_DIM = "#A9A3C9"
C_TEXT_MUTED = "#736D99"
C_ACCENT = "#8B5CF6"
C_ACCENT_LIGHT = "#A78BFA"
C_PANEL = "rgba(255, 255, 255, 0.055)"
C_PANEL_HOVER = "rgba(255, 255, 255, 0.09)"
C_BORDER = "rgba(168, 148, 255, 0.22)"
C_BORDER_HOVER = "rgba(167, 139, 250, 0.55)"

RADIUS_PANEL = 18
RADIUS_CARD = 16
RADIUS_BUTTON = 12

FONT_FAMILY = "Segoe UI Variable Display"
FONT_FALLBACK = "Segoe UI"


def resolve_font_family() -> str:
    """Возвращает доступное семейство: Variable Display есть только на Win11."""
    families = set(QFontDatabase.families())
    if FONT_FAMILY in families:
        return FONT_FAMILY
    return FONT_FALLBACK


def font(size: int = 10, weight: QFont.Weight = QFont.Weight.Normal,
         letter_spacing: float = 0.0) -> QFont:
    f = QFont(resolve_font_family(), size)
    f.setWeight(weight)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    if letter_spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, letter_spacing)
    return f


def app_stylesheet() -> str:
    """Глобальные стили: скроллбары, поля ввода, подсказки."""
    return f"""
    QWidget {{
        color: {C_TEXT};
        font-family: "{resolve_font_family()}";
    }}
    QToolTip {{
        background-color: #1B1436;
        color: {C_TEXT};
        border: 1px solid {C_BORDER_HOVER};
        border-radius: 8px;
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
    QLineEdit:focus {{ border: 1px solid {C_BORDER_HOVER}; }}
    QComboBox {{
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid {C_BORDER};
        border-radius: 10px;
        padding: 7px 12px;
    }}
    QComboBox:hover {{ border: 1px solid {C_BORDER_HOVER}; }}
    QComboBox QAbstractItemView {{
        background: #150F2E;
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
    QCheckBox::indicator:checked {{
        background: {C_ACCENT};
        border: 1px solid {C_ACCENT_LIGHT};
    }}
    """
