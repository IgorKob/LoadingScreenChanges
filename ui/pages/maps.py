"""Страница «Карты»: каталог из 33 карт с миниатюрами и действиями."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..widgets import Badge, GhostButton, GlassPanel, IconButton, Thumb, draw_icon, rounded_path
from .base import Page, header
from .preview import PreviewDialog

FILTERS = [
    ("all", "Все ресурсы"),
    ("assigned", "Назначенные"),
    ("empty", "Неназначенные"),
    ("pending", "Требуют применения"),
    ("missing", "Недоступные"),
]


class MapCard(GlassPanel):
    """Карточка карты: миниатюра оригинала, статус и действия."""

    def __init__(self, page: "MapsPage", entry: dict):
        super().__init__(page, radius=theme.RADIUS_CARD, hoverable=True)
        self.page = page
        self.entry = entry
        self.code = entry["code"]
        self.setMinimumHeight(250)
        self.setMinimumWidth(270)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(8)

        self.thumb = Thumb(self, radius=10, placeholder="оригинал не найден")
        self.thumb.setFixedHeight(104)
        layout.addWidget(self.thumb)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        self.title = QLabel(entry["name"])
        self.title.setFont(theme.font(10, QFont.Weight.DemiBold))
        self.title.setStyleSheet(f"color: {theme.C_TEXT};")
        title_row.addWidget(self.title)
        title_row.addStretch(1)
        self.badge = Badge("нет", self, theme.TEXT_MUTED)
        title_row.addWidget(self.badge)
        layout.addLayout(title_row)

        self.hint = QLabel("")
        self.hint.setFont(theme.font(8))
        self.hint.setStyleSheet(f"color: {theme.C_TEXT_MUTED};")
        layout.addWidget(self.hint)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self.choose = GhostButton("Выбрать", self, height=32)
        self.choose.clicked.connect(self._choose)
        buttons.addWidget(self.choose)
        self.preview = IconButton("image", self, size=32, tooltip="Предпросмотр")
        self.preview.clicked.connect(self._preview)
        buttons.addWidget(self.preview)
        self.reset = IconButton("trash", self, size=32, tooltip="Сбросить назначение")
        self.reset.clicked.connect(self._reset)
        buttons.addWidget(self.reset)
        layout.addLayout(buttons)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        assignment = self.page.controller.assignment(self.code)
        has_image = bool(assignment.get("image"))
        applied = bool(assignment.get("applied"))
        resource = self.page.controller.scan.maps.get(self.code)
        files = len(resource.files) if resource else 0

        if not files:
            self.badge.set_state("недоступна", theme.TEXT_MUTED)
            self.hint.setText("Ресурс не найден в игре")
        elif applied:
            self.badge.set_state("применено", theme.TEAL)
            self.hint.setText(f"Файлов ресурса: {files}")
        elif has_image:
            self.badge.set_state("готово", theme.ACCENT_LIGHT)
            self.hint.setText(f"Файлов ресурса: {files}")
        else:
            self.badge.set_state("не назначено", theme.TEXT_DIM)
            self.hint.setText(f"Файлов ресурса: {files}")

        self.choose.setText("Заменить" if has_image else "Выбрать")
        self.reset.setEnabled(has_image)
        self.setToolTip(assignment.get("image", ""))
        self.update()

    def load_thumb(self) -> None:
        resource = self.page.controller.scan.maps.get(self.code)
        if resource and resource.primary:
            pixmap = self.page.controller.thumbs.get(f"game:{self.code}", resource.primary)
            self.thumb.set_pixmap(pixmap)
        self.refresh()

    # ------------------------------------------------------------ действия
    def _choose(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, f"Изображение для «{self.entry['name']}»", "",
            "Изображения (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not path:
            return
        try:
            self.page.controller.assign(self.code, path)
            self.page.window.show_toast("Изображение назначено. Не забудьте применить изменения",
                                        "info")
        except Exception as exc:  # noqa: BLE001
            self.page.window.show_toast(str(exc), "error")
        self.refresh()

    def _reset(self) -> None:
        self.page.controller.reset_assignment(self.code)
        self.refresh()

    def _preview(self) -> None:
        PreviewDialog.show_for(self.page, self.code, self.entry["name"])


class MapsPage(Page):
    def __init__(self, controller, window):
        super().__init__(controller, window, title="Карты",
                         subtitle="Загрузочные экраны 33 карт классического режима 7×7")
        self.cards: dict[str, MapCard] = {}
        self._query = ""
        self._filter = "all"
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(220)
        self._search_timer.timeout.connect(self._rebuild)
        self._build()
        controller.scan_finished.connect(self.refresh)

    # ------------------------------------------------------------------
    def _build(self) -> None:
        toolbar = QWidget()
        toolbar.setStyleSheet("background: transparent;")
        row = QHBoxLayout(toolbar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        self.search = QLineEdit(toolbar)
        self.search.setPlaceholderText("Поиск по названию карты")
        self.search.setFixedHeight(38)
        self.search.textChanged.connect(self._on_search)
        row.addWidget(self.search, 3)

        self.filter_box = QComboBox(toolbar)
        self.filter_box.setFixedHeight(38)
        self.filter_box.setFixedWidth(240)
        for key, label in FILTERS:
            self.filter_box.addItem(label, key)
        self.filter_box.currentIndexChanged.connect(self._on_filter)
        row.addWidget(self.filter_box, 1)

        self.rescan_button = GhostButton("Сканировать ресурсы", toolbar, icon="refresh", height=38)
        self.rescan_button.clicked.connect(self.controller.rescan)
        row.addWidget(self.rescan_button)
        self.add(toolbar, animate=False)

        self.grid_host = QWidget()
        self.grid_host.setStyleSheet("background: transparent;")
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(12)
        self.add(self.grid_host, animate=False)

        self.empty_label = QLabel("Ничего не найдено по выбранному фильтру.")
        self.empty_label.setFont(theme.font(9))
        self.empty_label.setStyleSheet(f"color: {theme.C_TEXT_MUTED}; margin: 12px 6px;")
        self.empty_label.setVisible(False)
        self.add(self.empty_label, animate=False)

        self._rebuild()

    def _on_search(self, text: str) -> None:
        self._query = text.strip().lower()
        self._search_timer.start()

    def _on_filter(self, index: int) -> None:
        self._filter = self.filter_box.itemData(index) or "all"
        self._rebuild()

    def _matches(self, entry: dict) -> bool:
        if self._query and self._query not in entry["name"].lower() and self._query not in entry["code"]:
            return False
        assignment = self.controller.assignment(entry["code"])
        resource = self.controller.scan.maps.get(entry["code"])
        files = len(resource.files) if resource else 0
        has_image = bool(assignment.get("image"))
        applied = bool(assignment.get("applied"))

        if self._filter == "assigned":
            return has_image
        if self._filter == "empty":
            return not has_image
        if self._filter == "pending":
            return has_image and not applied
        if self._filter == "missing":
            return files == 0
        return True

    def _rebuild(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self.cards.clear()

        visible = [item for item in self.controller.maps if self._matches(item)]
        columns = 3
        for index, entry in enumerate(visible):
            card = MapCard(self, entry)
            card.refresh()
            self.grid.addWidget(card, index // columns, index % columns)
            self.cards[entry["code"]] = card
        for column in range(columns):
            self.grid.setColumnStretch(column, 1)
        self.empty_label.setVisible(not visible)
        for index, card in enumerate(self.cards.values()):
            QTimer.singleShot(30 + index * 12, card.load_thumb)

    # ------------------------------------------------------------- данные
    def refresh(self) -> None:
        for card in self.cards.values():
            card.refresh()
        if not self.cards:
            self._rebuild()

    def on_show(self) -> None:
        self._rebuild()
        super().on_show()
        # миниатюры грузим после появления страницы, чтобы не задерживать переход
        for index, card in enumerate(self.cards.values()):
            QTimer.singleShot(30 + index * 12, card.load_thumb)

