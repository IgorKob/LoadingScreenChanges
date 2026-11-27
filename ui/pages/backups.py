"""Страница «Резервные копии»: список копий и восстановление."""
from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .. import theme
from ..widgets import GhostButton, GlassPanel
from .base import Page
from utils import human_size


class BackupRow(GlassPanel):
    """Строка списка резервных копий."""

    def __init__(self, page: "BackupsPage", item: dict):
        super().__init__(page, radius=theme.RADIUS_CARD, hoverable=True)
        self.page = page
        self.item = item
        self.setMinimumHeight(66)

        row = QHBoxLayout(self)
        row.setContentsMargins(18, 10, 14, 10)
        row.setSpacing(12)

        text = QWidget()
        text.setStyleSheet("background: transparent;")
        column = QVBoxLayout(text)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(2)

        name = QLabel(item.get("map") or item.get("code", ""))
        name.setFont(theme.font(10, QFont.Weight.DemiBold))
        name.setStyleSheet(f"color: {theme.C_TEXT};")
        column.addWidget(name)

        when = time.strftime("%d.%m.%Y %H:%M", time.localtime(item.get("created_at", 0)))
        detail = QLabel(f"{when} · файлов: {item.get('files', 0)} · "
                        f"{human_size(int(item.get('size') or 0))}")
        detail.setFont(theme.font(8))
        detail.setStyleSheet(f"color: {theme.C_TEXT_MUTED};")
        column.addWidget(detail)

        row.addWidget(text, 1)

        restore = GhostButton("Восстановить", self, icon="refresh", height=34)
        restore.clicked.connect(lambda: page.restore_one(item["code"]))
        row.addWidget(restore)


class BackupsPage(Page):
    def __init__(self, controller, window):
        super().__init__(controller, window, title="Резервные копии",
                         subtitle="Оригинальные файлы сохраняются перед первой заменой")
        self._rows_host = QWidget()
        self._rows_host.setStyleSheet("background: transparent;")
        self._rows = QVBoxLayout(self._rows_host)
        self._rows.setContentsMargins(0, 0, 0, 0)
        self._rows.setSpacing(8)

        self.toolbar = QWidget()
        self.toolbar.setStyleSheet("background: transparent;")
        toolbar = QHBoxLayout(self.toolbar)
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.addStretch(1)
        self.restore_all_button = GhostButton("Восстановить всё", self.toolbar,
                                              icon="refresh", height=38)
        self.restore_all_button.clicked.connect(self.controller.restore_everything)
        toolbar.addWidget(self.restore_all_button)

        self.add(self.toolbar, animate=False)
        self.add(self._rows_host, animate=False)
        self.empty = QLabel("Резервных копий пока нет. Они появятся после первого применения.")
        self.empty.setFont(theme.font(9))
        self.empty.setStyleSheet(f"color: {theme.C_TEXT_MUTED}; margin: 10px 6px;")
        self.add(self.empty, animate=False)
        controller.restore_finished.connect(self.refresh)

    # ------------------------------------------------------------------
    def restore_one(self, code: str) -> None:
        self.controller.restore([code])

    def refresh(self) -> None:
        while self._rows.count():
            item = self._rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        items = self.controller.backup_items()
        for item in items:
            self._rows.addWidget(BackupRow(self, item))
        self.empty.setVisible(not items)
        self.restore_all_button.setEnabled(bool(items))

    def on_show(self) -> None:
        self.refresh()
        super().on_show()
