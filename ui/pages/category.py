"""Страницы категорий: гараж и элементы интерфейса на реальных ресурсах игры."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..widgets import Badge, GhostButton, GlassPanel, IconButton, Thumb, draw_icon
from .preview import PreviewDialog
from .base import Page

PAGE_SIZE = 24
FILTERS = [
    ("all", "Все ресурсы"),
    ("assigned", "Назначенные"),
    ("empty", "Неназначенные"),
    ("missing", "Недоступные"),
]


class ResourceCard(GlassPanel):
    """Карточка игрового изображения."""

    def __init__(self, page: "CategoryPage", entry: dict):
        super().__init__(page, radius=theme.RADIUS_CARD, hoverable=True)
        self.page = page
        self.entry = entry
        self.code = entry["id"]
        self.setMinimumHeight(196)
        self.setMinimumWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 8)
        layout.setSpacing(6)

        self.thumb = Thumb(self, radius=9, placeholder="нет файла")
        self.thumb.setFixedHeight(88)
        layout.addWidget(self.thumb)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        self.title = QLabel()
        self.title.setFont(theme.font(9, QFont.Weight.DemiBold))
        self.title.setStyleSheet(f"color: {theme.C_TEXT};")
        title_row.addWidget(self.title, 1)
        self.badge = Badge("—", self, theme.TEXT_MUTED)
        title_row.addWidget(self.badge)
        layout.addLayout(title_row)

        self.subtitle = QLabel()
        self.subtitle.setFont(theme.font(8))
        self.subtitle.setStyleSheet(f"color: {theme.C_TEXT_MUTED};")
        layout.addWidget(self.subtitle)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self.choose = GhostButton("Выбрать", self, height=30)
        self.choose.clicked.connect(self._choose)
        buttons.addWidget(self.choose, 1)
        self.preview = IconButton("image", self, size=30, tooltip="Предпросмотр замены")
        self.preview.clicked.connect(self._preview)
        buttons.addWidget(self.preview)
        self.reset = IconButton("trash", self, size=30, tooltip="Сбросить назначение")
        self.reset.clicked.connect(self._reset)
        buttons.addWidget(self.reset)
        layout.addLayout(buttons)

        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        assignment = self.page.controller.assignment(self.code)
        has_image = bool(assignment.get("image"))
        applied = bool(assignment.get("applied"))

        label = self.entry.get("name", "")
        metrics = QFontMetrics(self.title.font())
        self.title.setText(metrics.elidedText(label, Qt.TextElideMode.ElideRight, 150))
        self.title.setToolTip(label)

        folder = Path(self.entry.get("rel", "")).parent.name
        variants = int(self.entry.get("variants", 1) or 1)
        suffix = f" · ×{variants}" if variants > 1 else ""
        self.subtitle.setText(f"{folder} · {self.entry.get('format', '')}{suffix}")
        paths = [item.get("rel", "") for item in (self.entry.get("files") or [])]
        self.subtitle.setToolTip("\n".join(paths) or self.entry.get("rel", ""))

        if applied:
            self.badge.set_state("применено", theme.TEAL)
        elif has_image:
            self.badge.set_state("готово", theme.ACCENT_LIGHT)
        else:
            self.badge.set_state("не назначено", theme.TEXT_DIM)
        self.choose.setText("Заменить" if has_image else "Выбрать")
        self.reset.setEnabled(has_image)

    def load_thumb(self) -> None:
        path = self.entry.get("path")
        if path and Path(path).is_file():
            self.thumb.set_pixmap(self.page.controller.thumbs.get(f"img:{self.code}", path))

    # ------------------------------------------------------------ действия
    def _choose(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите изображение", "",
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

    def _preview(self) -> None:
        PreviewDialog.show_for(self.page, self.code,
                               self.entry.get("name", ""))

    def _reset(self) -> None:
        self.page.controller.reset_assignment(self.code)
        self.refresh()


class CategoryPage(Page):
    """Общий список ресурсов одной категории с поиском и постраничным выводом."""

    def __init__(self, controller, window, *, key: str, title: str,
                 subtitle: str, icon: str = "image"):
        super().__init__(controller, window, title=title, subtitle=subtitle)
        self.key = key
        self.icon_kind = icon
        self._query = ""
        self._filter = "all"
        self._shown = PAGE_SIZE
        self._cards: list[ResourceCard] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(220)
        self._timer.timeout.connect(self._rebuild)
        self._build()
        controller.images_scanned.connect(self.refresh)
        controller.assignments_changed.connect(self.refresh)

    # ------------------------------------------------------------------
    def _build(self) -> None:
        toolbar = QWidget()
        toolbar.setStyleSheet("background: transparent;")
        row = QHBoxLayout(toolbar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        self.search = QLineEdit(toolbar)
        self.search.setPlaceholderText("Поиск по названию файла")
        self.search.setFixedHeight(38)
        self.search.textChanged.connect(self._on_search)
        row.addWidget(self.search, 3)

        self.filter_box = QComboBox(toolbar)
        self.filter_box.setFixedHeight(38)
        self.filter_box.setFixedWidth(220)
        for key, label in FILTERS:
            self.filter_box.addItem(label, key)
        self.filter_box.currentIndexChanged.connect(self._on_filter)
        row.addWidget(self.filter_box)

        self.rescan = GhostButton("Индексировать заново", toolbar, icon="refresh", height=38)
        self.rescan.clicked.connect(self.controller.scan_images)
        row.addWidget(self.rescan)
        self.add(toolbar, animate=False)

        self.notice = QLabel("")
        self.notice.setFont(theme.font(9))
        self.notice.setStyleSheet(f"color: {theme.C_TEXT_DIM}; margin-left: 6px;")
        self.notice.setWordWrap(True)
        self.add(self.notice, animate=False)

        self.grid_host = QWidget()
        self.grid_host.setStyleSheet("background: transparent;")
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(10)
        self.add(self.grid_host, animate=False)

        self.more = GhostButton("Показать ещё", self, height=36)
        self.more.clicked.connect(self._show_more)
        self.add(self.more, animate=False)

    # ----------------------------------------------------------- фильтры
    def _on_search(self, text: str) -> None:
        self._query = text.strip().lower()
        self._shown = PAGE_SIZE
        self._timer.start()

    def _on_filter(self, index: int) -> None:
        self._filter = self.filter_box.itemData(index) or "all"
        self._shown = PAGE_SIZE
        self._rebuild()

    def _show_more(self) -> None:
        self._shown += PAGE_SIZE
        self._rebuild()

    def _matches(self, entry: dict) -> bool:
        haystack = f"{entry.get('name', '')} {entry.get('rel', '')}".lower()
        if self._query and self._query not in haystack:
            return False
        assignment = self.controller.assignment(entry["id"])
        has_image = bool(assignment.get("image"))
        if self._filter == "assigned":
            return has_image
        if self._filter == "empty":
            return not has_image
        if self._filter == "missing":
            return not Path(entry.get("path", "")).is_file()
        return True

    # ------------------------------------------------------------- вывод
    def _rebuild(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self._cards.clear()

        items = self.controller.images_in(self.key)
        if not items:
            self._update_notice(0)
            return

        visible = [entry for entry in items if self._matches(entry)]
        visible.sort(key=lambda entry: entry.get("name", ""))
        page = visible[: self._shown]

        columns = 4
        for index, entry in enumerate(page):
            card = ResourceCard(self, entry)
            self.grid.addWidget(card, index // columns, index % columns)
            self._cards.append(card)
        for column in range(columns):
            self.grid.setColumnStretch(column, 1)
        self._update_notice(len(visible))
        self.more.setVisible(len(visible) > len(page))
        self._schedule_thumbs()
        self.grid_host.update()

    def _schedule_thumbs(self) -> None:
        """Подгружает миниатюры порциями, чтобы не блокировать интерфейс."""
        for index, card in enumerate(self._cards):
            QTimer.singleShot(20 + index * 25, card.load_thumb)

    def _update_notice(self, count: int) -> None:
        total = len(self.controller.images_in(self.key))
        if total == 0:
            if self.controller.busy_images:
                self.notice.setText("Индексируем ресурсы игры…")
            elif not self.controller.game or not self.controller.game.found:
                self.notice.setText(
                    "Игра не найдена. Укажите папку с Tanks Blitz в настройках, "
                    "и ресурсы проиндексируются автоматически.")
            else:
                self.notice.setText("Ресурсы этой категории не найдены в установленной игре.")
        elif count == 0:
            self.notice.setText("По выбранному фильтру ничего не найдено.")
        else:
            self.notice.setText(
                f"Всего в категории: {total} · показано: {min(self._shown, count)}")

    def refresh(self) -> None:
        """Обновляет статусы карточек, не пересоздавая сетку."""
        if not self._cards:
            self._rebuild()
            return
        for card in self._cards:
            card.refresh()

    def on_show(self) -> None:
        if not self._cards:
            self._rebuild()
        else:
            self._schedule_thumbs()
        super().on_show()
