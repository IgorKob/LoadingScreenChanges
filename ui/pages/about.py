"""Страница «О программе»: версия, список изменений, совместимость."""
from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .. import theme
from ..widgets import GlassPanel
from .base import Page

CHANGELOG = [
    ("0.4", [
        "Новый интерфейс Liquid Glass на PySide6: боковая навигация, стеклянные "
        "панели, градиентный заголовок, плавные переходы.",
        "Разделы «Гараж» и «Элементы интерфейса»: индексация реальных ресурсов игры "
        "(DVPL type0), поиск и фильтры по 4000+ изображениям.",
        "Применение изменений без модальных окон: состояние отображается прямо "
        "в панели действий.",
        "Настройка анимаций: полные, уменьшенные или отключённые.",
        "Поиск и фильтрация карт, предпросмотр и сброс назначения.",
        "Окно открывается развёрнутым и запоминает своё состояние.",
    ]),
    ("0.3", [
        "Каталог из 33 карт, автоматический поиск игры, сканирование ресурсов.",
        "Замена загрузочных экранов с резервными копиями и откатом.",
        "Предпросмотр и сброс назначенных изображений.",
    ]),
]

COMPATIBILITY = [
    "Windows 10 и Windows 11, x64",
    "Tanks Blitz (Lesta), классический режим 7×7",
    "Форматы изображений: PNG, JPG/JPEG, WEBP, BMP",
    "Ресурсы игры: контейнер DVPL с WebP внутри",
]


class AboutPage(Page):
    def __init__(self, controller, window):
        super().__init__(controller, window, title="О программе",
                         subtitle="Версия, изменения и совместимость")
        self._build()

    def _build(self) -> None:
        info = GlassPanel(self, radius=theme.RADIUS_PANEL)
        column = QVBoxLayout(info)
        column.setContentsMargins(24, 20, 24, 20)
        column.setSpacing(6)

        name = QLabel("BlitzCustom")
        name.setFont(theme.font(18, QFont.Weight.Bold))
        name.setStyleSheet(f"color: {theme.C_TEXT};")
        column.addWidget(name)

        version = QLabel(f"Версия {self.window.app_version}")
        version.setFont(theme.font(10))
        version.setStyleSheet(f"color: {theme.C_TEXT_DIM};")
        column.addWidget(version)

        description = QLabel(
            "Приложение для замены загрузочных экранов, фонов ангара и графики "
            "интерфейса Tanks Blitz на собственные. Все изменения обратимы, "
            "оригиналы сохраняются в резервных копиях.")
        description.setFont(theme.font(9))
        description.setStyleSheet(f"color: {theme.C_TEXT_DIM};")
        description.setWordWrap(True)
        column.addWidget(description)
        self.add(info)

        changelog = GlassPanel(self, radius=theme.RADIUS_PANEL)
        column = QVBoxLayout(changelog)
        column.setContentsMargins(24, 18, 24, 18)
        column.setSpacing(8)

        title = QLabel("Список изменений")
        title.setFont(theme.font(11, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {theme.C_TEXT};")
        column.addWidget(title)

        for version, items in CHANGELOG:
            caption = QLabel(f"Версия {version}")
            caption.setFont(theme.font(9, QFont.Weight.DemiBold))
            caption.setStyleSheet(f"color: {theme.C_ACCENT_LIGHT};")
            column.addWidget(caption)
            for item in items:
                line = QLabel(f"•  {item}")
                line.setFont(theme.font(9))
                line.setStyleSheet(f"color: {theme.C_TEXT_DIM};")
                line.setWordWrap(True)
                column.addWidget(line)
        self.add(changelog)

        compatible = GlassPanel(self, radius=theme.RADIUS_PANEL)
        column = QVBoxLayout(compatible)
        column.setContentsMargins(24, 18, 24, 18)
        column.setSpacing(6)

        title = QLabel("Совместимость")
        title.setFont(theme.font(11, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {theme.C_TEXT};")
        column.addWidget(title)

        for item in COMPATIBILITY:
            line = QLabel(f"•  {item}")
            line.setFont(theme.font(9))
            line.setStyleSheet(f"color: {theme.C_TEXT_DIM};")
            column.addWidget(line)

        note = QLabel(
            "Декоративная иллюстрация персонажей не входит в поставку: положите "
            "свой файл assets/hero.png рядом с программой, и он появится в верхней "
            "области окна.")
        note.setFont(theme.font(8))
        note.setStyleSheet(f"color: {theme.C_TEXT_MUTED};")
        note.setWordWrap(True)
        column.addWidget(note)
        self.add(compatible)
