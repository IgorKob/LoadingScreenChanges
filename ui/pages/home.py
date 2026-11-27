"""Страница «Главная»: статус игры, сводка и быстрые действия."""
from __future__ import annotations

import time

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .. import theme
from ..animations import MOTION
from ..widgets import (
    AccentButton,
    GhostButton,
    GlassPanel,
    draw_icon,
    paint_gradient_text,
    rounded_path,
)
from .base import Page


class GameStatusCard(GlassPanel):
    """Крупная карточка «Игра найдена» с путём и кнопкой перепроверки."""

    def __init__(self, page: "HomePage"):
        super().__init__(page, radius=theme.RADIUS_PANEL, hoverable=False)
        self.page = page
        self._found = False
        self._title = "Поиск игры…"
        self._path = "Определяем установленную игру"
        self.setMinimumHeight(92)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(84, 12, 18, 12)
        layout.setSpacing(12)
        layout.addStretch(1)

        self.button = GhostButton("Проверить снова", self, icon="search", height=40)
        self.button.clicked.connect(page.recheck)
        layout.addWidget(self.button)

    def set_result(self, found: bool, path: str, detail: str = "") -> None:
        self._found = found
        self._title = "Игра найдена!" if found else "Игра не найдена"
        self._path = path or "Путь не определён — укажите папку с игрой в настройках"
        self._detail = detail
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())

        circle = QRectF(24, rect.center().y() - 24, 48, 48)
        color = theme.TEAL if self._found else theme.AMBER
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 38))
        painter.drawEllipse(circle)
        painter.setPen(QColor(color.red(), color.green(), color.blue(), 150))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(circle.adjusted(0.5, 0.5, -0.5, -0.5))
        draw_icon(painter, "check" if self._found else "warn",
                  circle.adjusted(13, 13, -13, -13), color, 2.2)

        painter.setFont(theme.font(13, QFont.Weight.DemiBold))
        painter.setPen(theme.TEXT)
        painter.drawText(QRectF(88, rect.y() + 18, rect.width() - 260, 28),
                         int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                         self._title)

        painter.setFont(theme.font(9))
        painter.setPen(theme.TEXT_DIM)
        fm = QFontMetrics(painter.font())
        text = self._path
        available = int(rect.width() - 300)
        if fm.horizontalAdvance(text) > available > 0:
            text = fm.elidedText(text, Qt.TextElideMode.ElideMiddle, available)
        painter.drawText(QRectF(88, rect.y() + 46, rect.width() - 260, 22),
                         int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                         f"Путь: {text}")
        painter.end()


class QuickActions(GlassPanel):
    """Панель применения изменений со встроенными состояниями (ТЗ, раздел 8)."""

    STATE_IDLE = "idle"
    STATE_BUSY = "busy"
    STATE_SUCCESS = "success"
    STATE_ERROR = "error"

    def __init__(self, page: "HomePage"):
        super().__init__(page, radius=theme.RADIUS_PANEL)
        self.page = page
        self._state = self.STATE_IDLE
        self._status = ""
        self.setMinimumHeight(210)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(10)

        title = QLabel("Быстрые действия")
        title.setFont(theme.font(11, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {theme.C_TEXT};")
        layout.addWidget(title)

        body = QHBoxLayout()
        body.setSpacing(18)

        left = QVBoxLayout()
        left.setSpacing(10)
        self.apply_button = AccentButton("Применить изменения", self, icon="play", height=48)
        self.apply_button.clicked.connect(self._apply)
        left.addWidget(self.apply_button)

        self.restore_button = GhostButton("Восстановить оригиналы", self, icon="refresh", height=42)
        self.restore_button.clicked.connect(self._restore)
        left.addWidget(self.restore_button)

        self.status = QLabel("")
        self.status.setFont(theme.font(9))
        self.status.setStyleSheet(f"color: {theme.C_TEXT_DIM};")
        self.status.setWordWrap(True)
        left.addWidget(self.status)
        left.addStretch(1)

        self.details = GhostButton("Подробнее", self, height=30)
        self.details.clicked.connect(self._show_details)
        self.details.setVisible(False)
        left.addWidget(self.details)

        body.addLayout(left, 3)

        right = QVBoxLayout()
        right.setSpacing(8)
        hint = QLabel("Замените загрузочные изображения карт на свои "
                      "и сделайте игру ещё красивее!")
        hint.setFont(theme.font(10))
        hint.setStyleSheet(f"color: {theme.C_TEXT_DIM};")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        right.addWidget(hint)
        right.addStretch(1)
        body.addLayout(right, 2)

        layout.addLayout(body)
        layout.addStretch(1)

    # ------------------------------------------------------------------
    def set_state(self, state: str, message: str = "") -> None:
        self._state = state
        self._status = message
        self.status.setText(message)
        self.details.setVisible(state == self.STATE_ERROR)
        if state == self.STATE_BUSY:
            self.apply_button.set_state(AccentButton.STATE_BUSY)
            self.restore_button.setEnabled(False)
        elif state == self.STATE_SUCCESS:
            self.apply_button.set_state(AccentButton.STATE_SUCCESS)
            self.restore_button.setEnabled(True)
        elif state == self.STATE_ERROR:
            self.apply_button.set_state(AccentButton.STATE_ERROR, "Не удалось применить")
            self.restore_button.setEnabled(True)
        else:
            self.apply_button.reset_state()
            self.restore_button.setEnabled(True)
        self.update()

    def _apply(self) -> None:
        codes = self.page.controller.assigned_codes()
        if not codes:
            self.page.window.show_toast("Сначала назначьте изображения на вкладке «Карты».", "info")
            return
        self.set_state(self.STATE_BUSY, "Применение… основной интерфейс остаётся доступным")
        self.page.controller.apply(codes)

    def _restore(self) -> None:
        self.page.controller.restore_everything()

    def _show_details(self) -> None:
        summary = self.page.controller.last_apply or {}
        lines = []
        for item in summary.get("details", [])[:5]:
            if item.get("status") != "applied":
                lines.append(f"{item['code']}: {item.get('reason', 'ошибка')}")
        text = "; ".join(lines) if lines else "Подробности записаны в журнал операций."
        self.page.window.show_toast(text, "error")

    def paintEvent(self, event) -> None:
        if self._state == self.STATE_SUCCESS:
            self._fill = QColor(45, 212, 191, 34)
            self._border = QColor(45, 212, 191, 120)
        elif self._state == self.STATE_ERROR:
            self._fill = QColor(245, 158, 11, 30)
            self._border = QColor(245, 158, 11, 120)
        elif self._state == self.STATE_BUSY:
            self._fill = QColor(139, 92, 246, 34)
            self._border = QColor(167, 139, 250, 120)
        else:
            self._fill = theme.PANEL_FILL
            self._border = theme.PANEL_BORDER
        super().paintEvent(event)


class PreviewCard(GlassPanel):
    """Превью назначенной карты с «каруселью» и кнопкой выбора изображения."""

    def __init__(self, page: "HomePage"):
        super().__init__(page, radius=theme.RADIUS_PANEL, hoverable=True)
        self.page = page
        self._codes: list[str] = []
        self._index = 0
        self.setMinimumHeight(210)
        self.setMinimumWidth(260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)
        layout.addStretch(1)

        row = QHBoxLayout()
        row.addStretch(1)
        self.edit = GhostButton("", self, icon="pencil", height=32, min_width=40)
        self.edit.setToolTip("Назначить изображение для этой карты")
        self.edit.clicked.connect(self._edit)
        row.addWidget(self.edit)
        layout.addLayout(row)

    def set_codes(self, codes: list[str]) -> None:
        self._codes = codes
        if self._index >= len(codes):
            self._index = 0
        self.update()

    def _current(self) -> str | None:
        if not self._codes:
            return None
        return self._codes[self._index % len(self._codes)]

    def _edit(self) -> None:
        code = self._current()
        if code is None:
            self.page.window.show_toast("Пока нет назначенных изображений.", "info")
            return
        self.page.pick_image_for(code)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())

        code = self._current()
        thumb = QRectF(16, 16, rect.width() - 32, rect.height() - 64)
        pixmap = None
        if code:
            assignment = self.page.controller.assignment(code)
            image_path = assignment.get("image")
            if image_path:
                pixmap = self.page.controller.thumbs.get(f"user:{code}", image_path)
        path = rounded_path(thumb, 12)
        painter.setClipPath(path)
        if pixmap is not None and not pixmap.isNull():
            area = thumb.adjusted(6, 6, -6, -6)
            scaled = pixmap.scaled(area.size().toSize(),
                                   Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap(int(area.center().x() - scaled.width() / 2),
                               int(area.center().y() - scaled.height() / 2), scaled)
        else:
            painter.fillPath(path, QColor(255, 255, 255, 10))
            draw_icon(painter, "image",
                      QRectF(thumb.center().x() - 16, thumb.center().y() - 26, 32, 32),
                      QColor(255, 255, 255, 48), 1.6)
            painter.setFont(theme.font(8))
            painter.setPen(QColor(255, 255, 255, 60))
            painter.drawText(QRectF(thumb.x(), thumb.center().y() + 12, thumb.width(), 18),
                             int(Qt.AlignmentFlag.AlignCenter), "изображение не назначено")
        painter.setClipping(False)
        painter.setPen(QColor(255, 255, 255, 24))
        painter.drawPath(path)

        name = self.page.controller.map_name(code) if code else "Нет назначенных карт"
        painter.setFont(theme.font(10, QFont.Weight.DemiBold))
        painter.setPen(theme.TEXT)
        painter.drawText(QRectF(16, rect.bottom() - 40, rect.width() - 60, 22),
                         int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), name)

        total = min(len(self._codes), 4)
        if total > 1:
            for i in range(total):
                x = rect.center().x() - (total * 12) / 2 + i * 12
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(theme.ACCENT_LIGHT if i == self._index % total
                                 else QColor(255, 255, 255, 60))
                painter.drawEllipse(QRectF(x, rect.bottom() - 22, 6, 6))
        painter.end()


class RecentOps(QWidget):
    """Список последних операций (ТЗ, 4.1)."""

    def __init__(self, page: "HomePage"):
        super().__init__(page)
        self.page = page
        self.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self._layout = layout

    def set_rows(self, rows: list[dict]) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not rows:
            label = QLabel("Операций пока не было")
            label.setFont(theme.font(9))
            label.setStyleSheet(f"color: {theme.C_TEXT_MUTED}; margin-left: 16px;")
            self._layout.addWidget(label)
            return
        for record in rows[:4]:
            self._layout.addWidget(_op_row(record))


def _op_row(record: dict) -> QWidget:
    widget = QWidget()
    widget.setStyleSheet("background: transparent;")
    row = QHBoxLayout(widget)
    row.setContentsMargins(16, 6, 16, 6)
    row.setSpacing(10)

    failed = bool(record.get("errors"))
    color = theme.AMBER if failed else theme.TEAL
    row.addWidget(_OpIcon("warn" if failed else "check", color))

    if record.get("kind") == "restore":
        text = f"Восстановлено файлов: {record.get('restored', 0)}"
    else:
        text = f"Применено карт: {record.get('applied', 0)}"
    if failed:
        text += f" · ошибок: {record.get('errors')}"

    label = QLabel(text)
    label.setFont(theme.font(9))
    label.setStyleSheet(f"color: {theme.C_TEXT_DIM};")
    row.addWidget(label)
    row.addStretch(1)

    when = QLabel(time.strftime("%d.%m %H:%M", time.localtime(record.get("at", 0))))
    when.setFont(theme.font(8))
    when.setStyleSheet(f"color: {theme.C_TEXT_MUTED};")
    row.addWidget(when)
    return widget


class _OpIcon(QWidget):
    def __init__(self, kind: str, color: QColor):
        super().__init__()
        self.kind = kind
        self.color = color
        self.setFixedSize(18, 18)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        draw_icon(painter, self.kind, QRectF(1, 1, 16, 16), self.color, 1.6)
        painter.end()


class Tagline(QWidget):
    """Крупный слоган под заголовком страницы."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(74)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())

        title = QRectF(rect.x() + 6, rect.y() + 2, rect.width() - 12, 44)
        paint_gradient_text(painter, title, "Настрой игру под себя",
                            theme.font(24, QFont.Weight.Bold, 0.4),
                            QColor("#FFFFFF"), QColor("#A78BFA"),
                            glow=QColor(139, 92, 246, 120), align_center=False)

        painter.setFont(theme.font(9))
        painter.setPen(theme.C_TEXT_DIM)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 46, rect.width() - 16, 22),
                         int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                         "Загрузочные экраны, фон ангара и интерфейс — в вашем стиле")
        painter.end()


class HomePage(Page):
    def __init__(self, controller, window):
        super().__init__(controller, window)
        self._build()
        controller.detect_finished.connect(self.refresh)
        controller.scan_finished.connect(self.refresh)
        controller.assignments_changed.connect(self.refresh)
        controller.apply_finished.connect(self._on_apply_finished)
        controller.restore_finished.connect(self._on_restore_finished)

    # ------------------------------------------------------------------
    def _build(self) -> None:
        self.add(Tagline(self), animate=False)
        self.status_card = GameStatusCard(self)
        self.add(self.status_card)

        row = QHBoxLayout()
        row.setSpacing(12)
        self.quick = QuickActions(self)
        self.quick.setMaximumHeight(248)
        row.addWidget(self.quick, 3)
        self.preview = PreviewCard(self)
        self.preview.setMaximumHeight(248)
        row.addWidget(self.preview, 2)
        row.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.add_layout(row)

        self.ops_panel = GlassPanel(self, radius=theme.RADIUS_CARD)
        ops_layout = QVBoxLayout(self.ops_panel)
        ops_layout.setContentsMargins(0, 12, 0, 10)
        ops_layout.setSpacing(2)
        caption = QLabel("Последние операции")
        caption.setFont(theme.font(10, QFont.Weight.DemiBold))
        caption.setStyleSheet(f"color: {theme.C_TEXT_DIM}; margin-left: 16px;")
        ops_layout.addWidget(caption)
        self.ops = RecentOps(self)
        ops_layout.addWidget(self.ops)
        self.add(self.ops_panel)

    # ------------------------------------------------------------- данные
    def refresh(self) -> None:
        stats = self.controller.stats()
        self.status_card.set_result(stats.game_found, stats.game_path)
        self.preview.set_codes(self.controller.assigned_codes())
        self.ops.set_rows(self.controller.history)

    def on_show(self) -> None:
        self.refresh()
        super().on_show()

    # ------------------------------------------------------------ действия
    def recheck(self) -> None:
        self.status_card.set_result(False, "Идёт поиск установленной игры…")
        self.window.statusbar.set_status("Поиск игры…", "busy")
        self.controller.detect()

    def pick_image_for(self, code: str) -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите изображение", "",
            "Изображения (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not path:
            return
        try:
            self.controller.assign(code, path)
            self.window.show_toast("Изображение назначено. Не забудьте применить изменения",
                                   "info")
        except Exception as exc:  # noqa: BLE001
            self.window.show_toast(str(exc), "error")
        self.refresh()

    def _on_apply_finished(self, summary: dict) -> None:
        errors = summary.get("errors", 0)
        applied = summary.get("applied", 0)
        if errors:
            reason = ""
            for item in summary.get("details", []):
                if item.get("status") == "error":
                    reason = str(item.get("reason", ""))[:120]
                    break
            self.quick.set_state(QuickActions.STATE_ERROR, reason or "Часть изменений не применилась")
        else:
            self.quick.set_state(QuickActions.STATE_SUCCESS,
                                 f"Применено карт: {applied}. Восстановить можно на вкладке "
                                 f"«Резервные копии».")
            if MOTION.enabled:
                QTimer.singleShot(3000, lambda: self.quick.set_state(QuickActions.STATE_IDLE))
            else:
                self.quick.set_state(QuickActions.STATE_IDLE)

    def _on_restore_finished(self, summary: dict) -> None:
        restored = summary.get("restored", 0)
        errors = summary.get("errors") or []
        if errors:
            self.quick.set_state(QuickActions.STATE_ERROR, str(errors[0])[:120])
        else:
            self.quick.set_state(QuickActions.STATE_SUCCESS, f"Восстановлено файлов: {restored}")
            QTimer.singleShot(3000, lambda: self.quick.set_state(QuickActions.STATE_IDLE))
