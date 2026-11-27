"""Страница «Настройки»: путь к игре, обработка изображений, анимации."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..animations import MODE_FULL, MODE_OFF, MODE_REDUCED, MOTION
from ..widgets import GhostButton, GlassPanel
from .base import Page

ANIMATION_MODES = [
    (MODE_FULL, "Полные"),
    (MODE_REDUCED, "Уменьшенные"),
    (MODE_OFF, "Отключены"),
]
CROP_MODES = [("cover", "Заполнить с обрезкой"), ("contain", "Вписать целиком"),
              ("stretch", "Растянуть")]
QUALITY = [("85", "85 — меньше размер"), ("90", "90 — баланс"), ("95", "95 — лучше качество")]


class _Section(GlassPanel):
    def __init__(self, page: "SettingsPage", title: str, hint: str = ""):
        super().__init__(page, radius=theme.RADIUS_PANEL)
        self.column = QVBoxLayout(self)
        self.column.setContentsMargins(22, 16, 22, 18)
        self.column.setSpacing(10)

        caption = QLabel(title)
        caption.setFont(theme.font(11, QFont.Weight.DemiBold))
        caption.setStyleSheet(f"color: {theme.C_TEXT};")
        self.column.addWidget(caption)

        if hint:
            sub = QLabel(hint)
            sub.setFont(theme.font(8))
            sub.setStyleSheet(f"color: {theme.C_TEXT_MUTED};")
            sub.setWordWrap(True)
            self.column.addWidget(sub)

    def row(self, label: str, widget: QWidget) -> None:
        line = QWidget()
        line.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(line)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        caption = QLabel(label)
        caption.setFont(theme.font(9))
        caption.setStyleSheet(f"color: {theme.C_TEXT_DIM};")
        caption.setMinimumWidth(190)
        layout.addWidget(caption)
        layout.addWidget(widget, 1)
        self.column.addWidget(line)


class SettingsPage(Page):
    def __init__(self, controller, window):
        super().__init__(controller, window, title="Настройки",
                         subtitle="Путь к игре, обработка изображений и поведение интерфейса")
        self._build()
        controller.scan_finished.connect(self.refresh)

    def _build(self) -> None:
        # --- игра ---
        game_section = _Section(self, "Игра", "Папка, где находится tanksblitz.exe")
        self.path_edit = QLineEdit(self)
        self.path_edit.setReadOnly(True)
        self.path_edit.setFixedHeight(36)
        game_section.row("Путь к установленной игре", self.path_edit)

        buttons = QWidget()
        buttons.setStyleSheet("background: transparent;")
        row = QHBoxLayout(buttons)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.browse = GhostButton("Указать папку", buttons, icon="folder", height=36)
        self.browse.clicked.connect(self._browse)
        row.addWidget(self.browse)
        self.redetect = GhostButton("Найти автоматически", buttons, icon="search", height=36)
        self.redetect.clicked.connect(self._redetect)
        row.addWidget(self.redetect)
        self.rescan = GhostButton("Сканировать ресурсы", buttons, icon="refresh", height=36)
        self.rescan.clicked.connect(self.controller.rescan)
        row.addWidget(self.rescan)
        row.addStretch(1)
        game_section.row("Действия", buttons)
        self.add(game_section)

        # --- обработка ---
        processing = _Section(self, "Обработка изображений",
                              "Как подгонять ваше изображение под размер игрового файла")
        self.crop_box = QComboBox(self)
        self.crop_box.setFixedHeight(36)
        self.crop_box.setMaximumWidth(380)
        for key, label in CROP_MODES:
            self.crop_box.addItem(label, key)
        self.crop_box.currentIndexChanged.connect(self._save_processing)
        processing.row("Режим подгонки", self.crop_box)

        self.quality_box = QComboBox(self)
        self.quality_box.setFixedHeight(36)
        self.quality_box.setMaximumWidth(380)
        for key, label in QUALITY:
            self.quality_box.addItem(label, key)
        self.quality_box.currentIndexChanged.connect(self._save_processing)
        processing.row("Качество WebP", self.quality_box)

        self.backup_check = QCheckBox("Создавать резервную копию перед первой заменой", self)
        self.backup_check.setFont(theme.font(9))
        self.backup_check.stateChanged.connect(self._save_processing)
        processing.row("Резервные копии", self.backup_check)
        self.add(processing)

        # --- интерфейс ---
        interface = _Section(self, "Интерфейс и анимации",
                             "Отключение анимаций помогает на слабых машинах")
        self.anim_box = QComboBox(self)
        self.anim_box.setFixedHeight(36)
        self.anim_box.setMaximumWidth(380)
        for key, label in ANIMATION_MODES:
            self.anim_box.addItem(label, key)
        self.anim_box.currentIndexChanged.connect(self._save_animation)
        interface.row("Анимации", self.anim_box)
        self.add(interface)

        # --- данные ---
        data = _Section(self, "Пользовательские данные",
                        "Настройки, изображения и резервные копии хранятся отдельно от EXE")
        data_buttons = QWidget()
        data_buttons.setStyleSheet("background: transparent;")
        data_row = QHBoxLayout(data_buttons)
        data_row.setContentsMargins(0, 0, 0, 0)
        data_row.setSpacing(8)
        open_data = GhostButton("Открыть папку данных", data_buttons, icon="folder", height=36)
        open_data.clicked.connect(self._open_data_dir)
        data_row.addWidget(open_data)
        open_logs = GhostButton("Открыть журнал операций", data_buttons, icon="clock", height=36)
        open_logs.clicked.connect(self._open_logs)
        data_row.addWidget(open_logs)
        data_row.addStretch(1)
        data.row("Папки", data_buttons)
        self.add(data)

        self.hint = QLabel("")
        self.hint.setFont(theme.font(8))
        self.hint.setStyleSheet(f"color: {theme.C_TEXT_MUTED}; margin-left: 6px;")
        self.add(self.hint, animate=False)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        settings = self.controller.settings
        root = settings.get("game_root") or ""
        if not root and self.controller.game and self.controller.game.root:
            root = str(self.controller.game.root)
        self.path_edit.setText(root or "игра не найдена")

        version = settings.get("game_version") or ""
        found = self.controller.scan.found
        total = self.controller.scan.total
        parts = []
        if version:
            parts.append(f"версия игры: {version}")
        if found:
            parts.append(f"ресурсы: {found}/{total}")
        if self.controller.scan.error:
            parts.append(self.controller.scan.error)
        self.hint.setText(" · ".join(parts) if parts else "")

        self._load_processing()
        self._load_animation()

    def _load_processing(self) -> None:
        settings = self.controller.settings
        for box, key, default in (
            (self.crop_box, "crop_mode", "cover"),
            (self.quality_box, "quality", 90),
        ):
            value = settings.get(key, default)
            index = box.findData(str(value))
            box.blockSignals(True)
            box.setCurrentIndex(max(index, 0))
            box.blockSignals(False)
        self.backup_check.blockSignals(True)
        self.backup_check.setChecked(bool(settings.get("backup_enabled", True)))
        self.backup_check.blockSignals(False)

    def _load_animation(self) -> None:
        mode = self.controller.settings.get("animations", MODE_FULL)
        index = self.anim_box.findData(mode)
        self.anim_box.blockSignals(True)
        self.anim_box.setCurrentIndex(max(index, 0))
        self.anim_box.blockSignals(False)

    def _save_processing(self) -> None:
        settings = self.controller.settings
        settings.set("crop_mode", self.crop_box.currentData())
        try:
            settings.set("quality", int(self.quality_box.currentData()))
        except (TypeError, ValueError):
            settings.set("quality", 90)
        settings.set("backup_enabled", self.backup_check.isChecked())
        settings.save()

    def _save_animation(self) -> None:
        mode = self.anim_box.currentData() or MODE_FULL
        MOTION.set_mode(mode)
        self.controller.settings.set("animations", mode)
        self.controller.settings.save()
        self.window.show_toast(f"Анимации: {self.anim_box.currentText().lower()}", "info")

    def _browse(self) -> None:
        from game_detector import validate_game_root

        folder = QFileDialog.getExistingDirectory(self, "Папка с Tanks Blitz")
        if not folder:
            return
        info = validate_game_root(folder)
        if info is None:
            self.window.show_toast("В этой папке нет tanksblitz.exe.", "error")
            return
        self.controller.settings.set("game_root", str(info.root))
        self.controller.settings.save()
        self.window.show_toast("Путь к игре сохранён", "success")
        self.controller.detect()

    def _redetect(self) -> None:
        self.controller.settings.set("game_root", "")
        self.controller.settings.save()
        self.window.statusbar.set_status("Поиск игры…", "busy")
        self.controller.detect()

    def _open_data_dir(self) -> None:
        from utils import user_data_dir

        self._open(user_data_dir())

    def _open_logs(self) -> None:
        logs = self.controller.settings.logs_dir()
        self._open(logs)

    def _open(self, path: Path) -> None:
        try:
            os.startfile(str(path))  # noqa: S606 - открытие проводника по запросу
        except OSError as exc:
            self.window.show_toast(f"Не удалось открыть папку: {exc}", "error")

    def on_show(self) -> None:
        self.refresh()
        super().on_show()
