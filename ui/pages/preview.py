"""Предпросмотр: как будет выглядеть ресурс после замены."""
from __future__ import annotations

import io

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..widgets import GhostButton, Thumb


class PreviewDialog(QDialog):
    """Сравнение оригинала и результата с учётом режима подгонки."""

    def __init__(self, page, code: str, title: str):
        super().__init__(page)
        self.page = page
        self.code = code
        self.setWindowTitle(f"Предпросмотр — {title}")
        self.setMinimumSize(900, 620)
        self.setStyleSheet("QDialog { background: #120C2B; }")

        controller = page.controller
        entry = controller.images.get(code) or {}
        resource = controller.resource_for(code)
        target_path = resource.primary if resource is not None else entry.get("path", "")
        assignment = controller.assignment(code)
        user_image = assignment.get("image")

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        heading = QLabel(title)
        heading.setFont(theme.font(12, theme.QFont.Weight.DemiBold))
        heading.setStyleSheet(f"color: {theme.C_TEXT};")
        root.addWidget(heading)

        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(self._column("Сейчас в игре", self._original_pixmap(target_path)))
        row.addWidget(self._column("Будет после замены",
                                   self._result_pixmap(user_image, target_path)))
        root.addLayout(row, 1)

        hint = QLabel("Результат показан с учётом режима подгонки и качества из настроек."
                      if user_image else
                      "Изображение не назначено — показан только оригинал.")
        hint.setFont(theme.font(8))
        hint.setStyleSheet(f"color: {theme.C_TEXT_MUTED};")
        root.addWidget(hint)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close = GhostButton("Закрыть", self, height=36)
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        root.addLayout(buttons)

    # ------------------------------------------------------------------
    def _column(self, caption: str, pixmap: QPixmap | None) -> QWidget:
        box = QWidget()
        box.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel(caption)
        label.setFont(theme.font(9, theme.QFont.Weight.DemiBold))
        label.setStyleSheet(f"color: {theme.C_TEXT_DIM};")
        layout.addWidget(label)

        view = Thumb(box, radius=12, placeholder="нет изображения")
        view.setMinimumSize(QSize(380, 380))
        view.set_pixmap(pixmap)
        layout.addWidget(view, 1)
        return box

    def _original_pixmap(self, path: str) -> QPixmap | None:
        if not path:
            return None
        return self.page.controller.thumbs.get(f"orig-preview:{self.code}", path)

    def _result_pixmap(self, user_image: str | None, target_path: str) -> QPixmap | None:
        if not user_image or not target_path:
            return None
        try:
            from image_processor import game_image_size, prepare_image_bytes

            size = game_image_size(target_path)
            payload, _ = prepare_image_bytes(
                user_image, size,
                str(self.page.controller.settings.get("crop_mode", "cover")),
                int(self.page.controller.settings.get("quality", 90)),
            )
            image = QImage.fromData(payload, "WEBP")
            return QPixmap.fromImage(image)
        except Exception:  # noqa: BLE001
            return None

    @classmethod
    def show_for(cls, page, code: str, title: str) -> None:
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            dialog = cls(page, code, title)
        finally:
            QGuiApplication.restoreOverrideCursor()
        dialog.exec()
