"""Общая основа страниц: прокрутка, заголовок, отложенное появление карточек."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..animations import fade_in


class Page(QWidget):
    """Страница с вертикальной прокруткой и стандартными отступами."""

    def __init__(self, controller, window, *, title: str = "", subtitle: str = ""):
        super().__init__()
        self.controller = controller
        self.window = window
        self._cards: list[QWidget] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; }"
                                  "QScrollArea > QWidget > QWidget { background: transparent; }")
        self.scroll.viewport().setStyleSheet("background: transparent;")
        outer.addWidget(self.scroll)

        self.content = QWidget()
        self.content.setStyleSheet("background: transparent;")
        # Высота по содержимому: карточки не растягиваются на весь экран.
        self.content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.scroll.setWidget(self.content)

        self.body = QVBoxLayout(self.content)
        self.body.setContentsMargins(4, 6, 12, 10)
        self.body.setSpacing(14)

        if title:
            self.body.addWidget(header(title, subtitle))

    # ------------------------------------------------------------ карточки
    def add(self, widget: QWidget, *, animate: bool = True) -> QWidget:
        self.body.addWidget(widget)
        if animate:
            self._cards.append(widget)
        return widget

    def add_layout(self, layout) -> None:
        self.body.addLayout(layout)

    def animate_cards(self) -> None:
        """Появление карточек с небольшой задержкой друг за другом."""
        # Много карточек — без анимации: десятки одновременных эффектов
        # прозрачности заметно замедляют отрисовку.
        if len(self._cards) > 16:
            return
        for index, card in enumerate(self._cards):
            delay = 40 * index
            QTimer.singleShot(delay, lambda c=card: fade_in(c, 200))

    # -------------------------------------------------------------- хуки
    def on_show(self) -> None:
        self.animate_cards()

    def refresh(self) -> None:
        """Перечитать состояние после сканирования или применения."""


def header(title: str, subtitle: str = "") -> QWidget:
    widget = QWidget()
    widget.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(6, 2, 0, 2)
    layout.setSpacing(3)

    label = QLabel(title)
    label.setFont(theme.font(17, theme.QFont.Weight.DemiBold))
    label.setStyleSheet(f"color: {theme.C_TEXT};")
    layout.addWidget(label)

    if subtitle:
        sub = QLabel(subtitle)
        sub.setFont(theme.font(9))
        sub.setStyleSheet(f"color: {theme.C_TEXT_DIM};")
        sub.setWordWrap(True)
        layout.addWidget(sub)
    return widget


def section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setFont(theme.font(10, theme.QFont.Weight.DemiBold))
    label.setStyleSheet(f"color: {theme.C_TEXT_DIM};")
    return label


def spacer() -> QWidget:
    widget = QWidget()
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return widget
