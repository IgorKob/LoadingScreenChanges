"""Главное окно: фон, верхняя область с персонажами, боковая навигация.

Окно безрамочное с собственной строкой заголовка; изменение размера и
перетаскивание обрабатываются в nativeEvent через Win32, чтобы сохранить
стандартное поведение Windows (включая «прилипание» к краям).
"""
from __future__ import annotations

import base64
import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import (QEasingCurve, QEvent, QPoint, QPointF, QPropertyAnimation,
                            QRect, QRectF, QSize, QSizeF, Qt, QTimer, Property, Signal)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QFontMetricsF,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QApplication,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from utils import LOG

from . import sounds, theme
from .animations import DURATION_PAGE, MOTION, fade_in, fade_out
from .controller import AppController
from .widgets import (
    paint_liquid_glass,
    IconButton,
    NavButton,
    Toast,
    draw_icon,
    paint_gradient_text,
    rounded_path,
)

APP_TITLE = "BlitzCustom"
APP_SUBTITLE = "Замена загрузочных экранов и графики Tanks Blitz"
HERO_IMAGE = "assets/hero.png"

WIN_W, WIN_H = 1240, 820
MIN_W, MIN_H = 1060, 700


# --------------------------------------------------------------------------
# фон
# --------------------------------------------------------------------------
class Backdrop(QWidget):
    """Фон окна: иллюстрация из assets/hero.png под тёмным градиентом."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bg = None
        self._bg_scaled = None
        self._bg_for = QSize()
        self._load_background()

    def _scaled_background(self):
        """Масштабированный фон кэшируется: иначе он пересчитывается на каждый кадр."""
        if self._bg is None:
            return None
        if self._bg_scaled is None or self._bg_for != self.size():
            self._bg_scaled = self._bg.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            self._bg_for = self.size()
        return self._bg_scaled

    def _load_background(self) -> None:
        from PySide6.QtGui import QPixmap
        from utils import assets_dir

        base = assets_dir()
        for name in ("hero.webp", "hero.png"):
            path = base / name
            if not path.is_file():
                continue
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self._bg = pixmap
                return

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        rect = QRectF(self.rect())

        radius = float(getattr(self.window(), "_radius", 0) or 0)
        path = QPainterPath()
        path.addRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
        painter.setClipPath(path)

        base = QLinearGradient(rect.topLeft(), rect.bottomRight())
        base.setColorAt(0.0, theme.BG_TOP)
        base.setColorAt(0.45, theme.BG_MID)
        base.setColorAt(1.0, theme.BG_BOTTOM)
        painter.fillRect(rect, base)

        if self._bg is not None:
            scaled = self._scaled_background()
            if scaled is not None:
                painter.drawPixmap(int(-(scaled.width() - rect.width()) / 2),
                                   int(-(scaled.height() - rect.height()) / 2), scaled)

            # Иллюстрация остаётся видимой сверху и уходит в фон к середине окна.
            veil = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            veil.setColorAt(0.0, QColor(7, 5, 15, 92))
            veil.setColorAt(0.10, QColor(9, 6, 20, 130))
            veil.setColorAt(0.22, QColor(14, 9, 34, 224))
            veil.setColorAt(0.36, QColor(18, 12, 43, 250))
            veil.setColorAt(1.0, QColor(18, 12, 43, 255))
            painter.fillRect(rect, veil)
        else:
            glow1 = QRadialGradient(rect.width() * 0.18, rect.height() * 0.05, rect.width() * 0.55)
            glow1.setColorAt(0.0, QColor(96, 165, 250, 46))
            glow1.setColorAt(1.0, QColor(96, 165, 250, 0))
            painter.fillRect(rect, glow1)

            glow2 = QRadialGradient(rect.width() * 0.88, rect.height() * 0.10, rect.width() * 0.48)
            glow2.setColorAt(0.0, QColor(167, 139, 250, 50))
            glow2.setColorAt(1.0, QColor(167, 139, 250, 0))
            painter.fillRect(rect, glow2)

            glow3 = QRadialGradient(rect.width() * 0.55, rect.height() * 0.95, rect.width() * 0.60)
            glow3.setColorAt(0.0, QColor(139, 92, 246, 30))
            glow3.setColorAt(1.0, QColor(139, 92, 246, 0))
            painter.fillRect(rect, glow3)

        painter.setClipping(False)
        painter.setPen(QPen(QColor(168, 148, 255, 60), 1.0))
        painter.drawPath(path)
        painter.end()


# --------------------------------------------------------------------------
# строка заголовка
# --------------------------------------------------------------------------
class ContentSheet(QWidget):
    """Большая стеклянная пластина под рабочей областью."""

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = rounded_path(rect, 22)

        painter.fillPath(path, QColor(11, 7, 26, 118))

        pearl = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        pearl.setColorAt(0.0, QColor(255, 255, 255, 22))
        pearl.setColorAt(0.35, QColor(255, 255, 255, 6))
        pearl.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillPath(path, pearl)

        painter.save()
        painter.setClipPath(path)
        edge = QLinearGradient(rect.topLeft(), rect.topRight())
        edge.setColorAt(0.0, QColor(255, 255, 255, 0))
        edge.setColorAt(0.25, QColor(255, 255, 255, 110))
        edge.setColorAt(0.6, QColor(255, 255, 255, 140))
        edge.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(QPen(QBrush(edge), 1.2))
        painter.drawLine(QPointF(rect.left() + 10, rect.top() + 1),
                         QPointF(rect.right() - 10, rect.top() + 1))
        painter.restore()

        frame = QLinearGradient(rect.topLeft(), rect.bottomRight())
        frame.setColorAt(0.0, QColor(168, 148, 255, 90))
        frame.setColorAt(1.0, QColor(168, 148, 255, 34))
        painter.setPen(QPen(QBrush(frame), 1.0))
        painter.drawPath(path)
        painter.end()


class TitleBar(QWidget):
    """Перетаскивание окна и кнопки управления."""

    def __init__(self, window: "MainWindow"):
        super().__init__(window)
        self._window = window
        self.setFixedHeight(52)
        self.setMouseTracking(True)
        self._mark = self._load_mark()

        layout = QHBoxLayout(self)
        # Отступы держат кнопки вне невидимой рамки изменения размера:
        # иначе клики по краям окна уходят системе на ресайз.
        layout.setContentsMargins(24, 0, 20, 0)
        layout.setSpacing(8)
        layout.addStretch(1)

        self.btn_min = IconButton("minimize", self, size=30, tooltip="Свернуть")
        self.btn_max = IconButton("maximize", self, size=30, tooltip="Развернуть")
        self.btn_close = IconButton("close", self, size=30, tooltip="Закрыть",
                                    hover_color=QColor(220, 70, 90))
        self.btn_min.clicked.connect(window.showMinimized)
        self.btn_max.clicked.connect(window.toggle_maximized)
        self.btn_close.clicked.connect(window.close)
        for button in (self.btn_min, self.btn_max, self.btn_close):
            layout.addWidget(button)

    def _load_mark(self):
        """Небольшой логотип для строки заголовка."""
        from PySide6.QtGui import QPixmap
        from utils import assets_dir

        base = assets_dir()
        for name in ("icon.webp", "icon.png"):
            path = base / name
            if not path.is_file():
                continue
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                continue
            return pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
        return None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._window.windowHandle()
            if handle is not None:
                handle.startSystemMove()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._window.toggle_maximized()
            return
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())

        # логотип-знак
        mark = QRectF(20, rect.center().y() - 12, 24, 24)
        if self._mark is not None and not self._mark.isNull():
            painter.save()
            painter.setClipPath(rounded_path(mark, 7))
            painter.drawPixmap(mark.toRect(), self._mark)
            painter.restore()
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(139, 92, 246, 60))
            painter.drawRoundedRect(mark.adjusted(-3, -3, 3, 3), 9, 9)
            draw_icon(painter, "spark", mark, theme.ACCENT_LIGHT, 1.6)

        font = theme.font(10, QFont.Weight.DemiBold, 0.2)
        painter.setFont(font)
        painter.setPen(theme.TEXT)
        painter.drawText(QRectF(56, rect.top(), 420, rect.height()),
                         int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                         f"{APP_TITLE} v{self._window.app_version}")
        painter.end()


# --------------------------------------------------------------------------
# верхняя область с персонажами
# --------------------------------------------------------------------------
class Hero(QWidget):
    """Декоративная область: иллюстрация персонажей, логотип и подзаголовок.

    Иллюстрация берётся из assets/hero.png, если файл есть рядом с программой;
    иначе рисуется абстрактная композиция в той же палитре. Персонажи не
    перекрывают рабочую область: высота области фиксирована, а содержимое
    обрезается по границам (ТЗ, 2.2).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(240)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._paint_center(painter, QRectF(self.rect()))
        painter.end()

    def _paint_center(self, painter: QPainter, rect: QRectF) -> None:
        font_big = theme.font(46, QFont.Weight.Bold, 0.8)
        metrics = QFontMetricsF(font_big)
        width = metrics.horizontalAdvance(APP_TITLE)
        title_rect = QRectF(rect.center().x() - width / 2, rect.y() + 74, width, 64)

        paint_gradient_text(painter, title_rect, APP_TITLE, font_big,
                            QColor("#FFFFFF"), QColor("#A78BFA"),
                            glow=QColor(139, 92, 246, 160))



# --------------------------------------------------------------------------
# боковая навигация
# --------------------------------------------------------------------------
NAV_ITEMS = [
    ("home", "Главная", "home"),
    ("maps", "Карты", "map"),
    ("garage", "Ангар", "garage"),
    ("elements", "Элементы UI", "grid"),
    ("profile", "Фоны профиля", "spark"),
    ("flags", "Флаги", "shield"),
    ("camos", "Камуфляжи", "grid"),
    ("other", "Прочие", "image"),
    ("backups", "Резервные копии", "clock"),
    ("settings", "Настройки", "gear"),
    ("about", "О программе", "info"),
]


def _add_soft_shadow(widget) -> None:
    """Мягкая тень под стеклянной панелью (ТЗ: Y 10, blur 20)."""
    from PySide6.QtWidgets import QGraphicsDropShadowEffect
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(20)
    effect.setOffset(0, 10)
    effect.setColor(QColor(0, 0, 0, 90))
    widget.setGraphicsEffect(effect)


class Sidebar(QWidget):
    """Боковая панель с «жидкой» стеклянной подложкой активного пункта.

    По ТЗ подложка не меняет цвет у пункта, а перетекает к нему с небольшим
    перехлёстом (пружина OutBack), как капля жидкости.
    """

    navigate = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(226)
        self.buttons: dict[str, NavButton] = {}
        self._active_key = ""
        self._pill = QRectF()
        self._pill_cache = None
        self._pill_cache_size = QSize()
        self._morph = QPropertyAnimation(self, b"pill_rect", self)
        self._morph.setDuration(theme.MORPH_MS)
        self._morph.setEasingCurve(QEasingCurve.Type.OutBack)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 14)
        layout.setSpacing(4)

        for key, title, icon in NAV_ITEMS:
            button = NavButton(key, title, icon, self)
            button.clicked.connect(lambda _=False, k=key: self._on_pick(k))
            layout.addWidget(button)
            self.buttons[key] = button

        layout.addStretch(1)

    # --- анимируемая подложка ---
    def _get_pill(self) -> QRectF:
        return self._pill

    PAD = 14

    def _set_pill(self, value: QRectF) -> None:
        previous = QRectF(self._pill)
        self._pill = value
        # перерисовываем только полосу, которую подложка прошла
        region = previous.united(value).adjusted(-self.PAD, -self.PAD, self.PAD, self.PAD)
        self.update(region.toRect() if not region.isEmpty() else self.rect())

    pill_rect = Property(QRectF, _get_pill, _set_pill)

    def _target_rect(self, key: str) -> QRectF:
        button = self.buttons.get(key)
        if button is None or not button.isVisible():
            return QRectF()
        top_left = button.mapTo(self, QPoint(0, 0))
        return QRectF(QPointF(top_left), QSizeF(button.size()))

    def _on_pick(self, key: str) -> None:
        sounds.play("click")
        self.navigate.emit(key)

    def set_active(self, key: str) -> None:
        self._active_key = key
        for name, button in self.buttons.items():
            button.set_active(name == key)
        target = self._target_rect(key)
        if target.isNull():
            return
        self._morph.stop()
        if not MOTION.enabled or self._pill.isNull() or not self.isVisible():
            # упрощённый режим: без перетекания, просто появляемся на месте
            self._set_pill(target)
            return
        self._morph.setStartValue(self._pill)
        self._morph.setEndValue(target)
        self._morph.start()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._pill_cache = None
        if self._active_key:
            self._set_pill(self._target_rect(self._active_key))

    def _render_pill(self, size: QSize):
        """Стеклянная подложка рисуется один раз в картинку и переиспользуется."""
        ratio = self.devicePixelRatioF()
        pixmap = QPixmap(int((size.width() + 2 * self.PAD) * ratio),
                         int((size.height() + 2 * self.PAD) * ratio))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.translate(self.PAD, self.PAD)
        paint_liquid_glass(painter, QRectF(0.0, 0.0, size.width(), size.height()), 13,
                           tint=theme.ACCENT, strength=1.15,
                           hover=0.0, pressed=0.0, inner_shadow=False)
        painter.end()
        return pixmap

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = rounded_path(rect, 18)
        painter.fillPath(path, QColor(10, 7, 22, 132))

        # стеклянная подложка активного пункта
        if not self._pill.isNull():
            size = QSize(int(round(self._pill.width())), int(round(self._pill.height())))
            if self._pill_cache is None or size != self._pill_cache_size:
                self._pill_cache = self._render_pill(size)
                self._pill_cache_size = size
            painter.drawPixmap(int(round(self._pill.left())) - self.PAD,
                               int(round(self._pill.top())) - self.PAD,
                               self._pill_cache)

        painter.setPen(QPen(QColor(168, 148, 255, 44), 1.0))
        painter.drawPath(path)
        painter.end()


# --------------------------------------------------------------------------
# нижняя строка состояния
# --------------------------------------------------------------------------
class StatusBar(QWidget):
    """Нижняя строка: только индикатор состояния слева."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self._status = "Готов к работе"
        self._kind = "idle"

    def set_status(self, text: str, kind: str = "idle") -> None:
        self._status = text
        self._kind = kind
        self.update()

    def set_resources(self, text: str) -> None:
        """Оставлено для совместимости: правая часть строки убрана."""

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())
        painter.setPen(QColor(255, 255, 255, 16))
        painter.drawLine(QPoint(int(rect.x()) + 24, int(rect.y())),
                         QPoint(int(rect.right()) - 24, int(rect.y())))

        color = {"idle": theme.TEAL, "busy": theme.ACCENT_LIGHT,
                 "error": theme.AMBER, "ok": theme.TEAL}.get(self._kind, theme.TEAL)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QPoint(int(rect.x()) + 30, int(rect.center().y())), 4, 4)
        painter.setFont(theme.font(9))
        painter.setPen(theme.TEXT_DIM)
        painter.drawText(QRectF(rect.x() + 42, rect.y(), 520, rect.height()),
                         int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                         self._status)
        painter.end()


# --------------------------------------------------------------------------
# главное окно
# --------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self, controller: AppController, app_version: str = "0.4",
                 classic: bool = False):
        super().__init__()
        self.controller = controller
        self.app_version = app_version
        self.classic = classic
        self.setWindowTitle(f"{APP_TITLE} v{app_version}")
        self.setWindowIcon(self._build_icon())
        self.setMinimumSize(MIN_W, MIN_H)
        if not classic:
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self._radius = 18
        self._pressed_button: str | None = None

        self._build_ui()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self._restore_window_state()
        self._connect()
        QTimer.singleShot(120, self._initial_load)

    # ------------------------------------------------------------------ ui
    def _build_ui(self) -> None:
        central = Backdrop(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.hero = Hero(central)
        root.addWidget(self.hero)

        self.titlebar = TitleBar(self)
        self.titlebar.setParent(self.hero)
        self.titlebar.setGeometry(0, 0, self.width(), 52)
        self.titlebar.setVisible(not self.classic)
        self.titlebar.raise_()

        body = QWidget(central)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(14, 6, 14, 6)
        body_layout.setSpacing(12)

        self.sidebar = Sidebar(body)
        _add_soft_shadow(self.sidebar)
        body_layout.addWidget(self.sidebar)

        self.sheet = ContentSheet(body)
        _add_soft_shadow(self.sheet)
        sheet_layout = QVBoxLayout(self.sheet)
        sheet_layout.setContentsMargins(8, 8, 8, 8)
        self.stack = QStackedWidget(self.sheet)
        self.stack.setStyleSheet("background: transparent;")
        sheet_layout.addWidget(self.stack)
        body_layout.addWidget(self.sheet, 1)
        root.addWidget(body, 1)

        self.statusbar = StatusBar(central)
        root.addWidget(self.statusbar)

        self.pages: dict[str, QWidget] = {}
        self._create_pages()
        # сразу подсвечиваем пункт, который открыт при запуске,
        # а фокус отдаём содержимому — иначе кольцо фокуса висит на пункте меню
        self.sidebar.set_active("home")
        self.stack.setFocus()

    def _create_pages(self) -> None:
        from .pages.about import AboutPage
        from .pages.backups import BackupsPage
        from .pages.category import CategoryPage
        from .pages.home import HomePage
        from .pages.maps import MapsPage
        from .pages.settings import SettingsPage

        self.pages["home"] = HomePage(self.controller, self)
        self.pages["maps"] = MapsPage(self.controller, self)
        self.pages["garage"] = CategoryPage(
            self.controller, self, key="garage", title="Ангар",
            subtitle="Фоны ангара и элементы оформления из установленной игры",
            icon="garage")
        self.pages["elements"] = CategoryPage(
            self.controller, self, key="elements", title="Элементы интерфейса",
            subtitle="Иконки, изображения кнопок и панели игрового интерфейса",
            icon="grid")
        self.pages["other"] = CategoryPage(
            self.controller, self, key="other", title="Прочие изображения",
            subtitle="Ресурсы, которые не отнесены ни к одной подтверждённой категории",
            icon="image")
        self.pages["flags"] = CategoryPage(
            self.controller, self, key="flags", title="Флаги",
            subtitle="Флаги стран: выбранная картинка применяется ко всем размерам флага",
            icon="shield")
        self.pages["camos"] = CategoryPage(
            self.controller, self, key="camos", title="Камуфляжи",
            subtitle="Сетка камуфляжа для всех танков: замена применяется ко всем файлам рисунка",
            icon="grid")
        self.pages["profile"] = CategoryPage(
            self.controller, self, key="profile", title="Фоны профиля",
            subtitle="Скачанные фоны профиля из кэша игры — их иконки видно в хранилище",
            icon="spark")
        self.pages["backups"] = BackupsPage(self.controller, self)
        self.pages["settings"] = SettingsPage(self.controller, self)
        self.pages["about"] = AboutPage(self.controller, self)

        for key, page in self.pages.items():
            self.stack.addWidget(page)
            page.setProperty("page_key", key)

    def _build_icon(self):
        from PySide6.QtGui import QIcon, QPixmap
        from utils import assets_dir

        base = assets_dir()
        for name in ("icon.webp", "icon.png"):
            path = base / name
            if path.is_file():
                icon = QIcon(str(path))
                if not icon.isNull():
                    return icon
        ico = base / "icon.ico"
        if ico.is_file():
            icon = QIcon(str(ico))
            if not icon.isNull():
                return icon

        size = 64
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        grad = QLinearGradient(0, 0, size, size)
        grad.setColorAt(0.0, QColor("#6D28D9"))
        grad.setColorAt(1.0, QColor("#2DD4BF"))
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(2, 2, size - 4, size - 4), 16, 16)
        draw_icon(painter, "spark", QRectF(14, 14, size - 28, size - 28), QColor("#FFFFFF"), 3.0)
        painter.end()
        return QIcon(pixmap)

    # --------------------------------------------------------------- связи
    def _connect(self) -> None:
        self.sidebar.navigate.connect(self.navigate)
        c = self.controller
        c.scan_started.connect(lambda: self.statusbar.set_status("Сканирование ресурсов…", "busy"))
        c.scan_finished.connect(self.on_scan_finished)
        c.assignments_changed.connect(self.on_assignments_changed)
        c.apply_progress.connect(self.on_apply_progress)
        c.apply_finished.connect(self.on_apply_finished)
        c.restore_finished.connect(self.on_restore_finished)
        c.toast.connect(self.show_toast)
        self.navigate("home")

    def _initial_load(self) -> None:
        current = self.stack.currentWidget()
        if current is not None:
            self._shown(current)
        if self.controller.scan.maps:
            self.on_scan_finished()
        self.controller.detect()

    # ------------------------------------------------------------ действия
    def navigate(self, key: str) -> None:
        page = self.pages.get(key)
        if page is None:
            return
        current = self.stack.currentWidget()
        if current is page:
            return
        self.sidebar.set_active(key)
        # Переключение без эффекта прозрачности на всю страницу: большой
        # offscreen-буфер заметно тормозил отрисовку.
        self.stack.setCurrentWidget(page)
        self.stack.setFocus()
        self._shown(page)

    def _swap_to(self, page: QWidget) -> None:
        self.stack.setCurrentWidget(page)
        self._shown(page)

    def _shown(self, page: QWidget) -> None:
        hook = getattr(page, "on_show", None)
        if callable(hook):
            hook()

    def on_scan_finished(self) -> None:
        stats = self.controller.stats()
        if stats.resources_found:
            self.statusbar.set_status("Готов к работе", "ok")
        else:
            self.statusbar.set_status("Ресурсы не найдены", "error")
        self.statusbar.set_resources(
            f"Ресурсы найдены: {stats.resources_found}/{stats.resources_total}"
            if stats.resources_found else "Ресурсы не найдены")
        for page in self.pages.values():
            hook = getattr(page, "refresh", None)
            if callable(hook):
                hook()

    def on_assignments_changed(self) -> None:
        for key in ("home", "maps"):
            page = self.pages.get(key)
            hook = getattr(page, "refresh", None)
            if callable(hook):
                hook()

    def on_apply_progress(self, done: int, total: int) -> None:
        if total:
            self.statusbar.set_status(f"Применение… {min(done + 1, total)}/{total}", "busy")

    def on_apply_finished(self, summary: dict) -> None:
        applied = summary.get("applied", 0)
        errors = summary.get("errors", 0)
        if errors:
            self.statusbar.set_status(f"Ошибок: {errors}", "error")
        else:
            self.statusbar.set_status(f"Применено: {applied}", "ok")
        for page in self.pages.values():
            hook = getattr(page, "refresh", None)
            if callable(hook):
                hook()

    def on_restore_finished(self, summary: dict) -> None:
        restored = summary.get("restored", 0)
        self.statusbar.set_status(f"Восстановлено файлов: {restored}", "ok")
        for page in self.pages.values():
            hook = getattr(page, "refresh", None)
            if callable(hook):
                hook()

    def show_toast(self, text: str, kind: str = "info") -> None:
        Toast(self.centralWidget(), text, kind=kind)

    # ------------------------------------------------------------- окно
    def toggle_maximized(self) -> None:
        if self.isMaximized():
            self.showNormal()
            self.titlebar.btn_max.kind = "maximize"
        else:
            self.showMaximized()
            self.titlebar.btn_max.kind = "restore"
        self.titlebar.btn_max.update()

    def eventFilter(self, obj, event) -> bool:
        """Диагностика кликов в области заголовка.

        Пишет в журнал, куда именно попал курсор: по логу видно, дошёл ли клик
        до кнопки или его перехватила система.
        """
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
            try:
                global_pos = event.globalPosition().toPoint()
            except AttributeError:
                return False
            if self.isVisible() and self.frameGeometry().contains(global_pos):
                local = self.mapFromGlobal(global_pos)
                child = self.childAt(local)
                LOG.debug("mouse %s global=%s local=%s child=%s",
                          event.type().name, global_pos, local,
                          type(child).__name__ if child is not None else None)
        return super().eventFilter(obj, event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "titlebar"):
            self.titlebar.setGeometry(0, 0, self.width(), 52)
            self.titlebar.raise_()

    def changeEvent(self, event) -> None:
        # скругление окна: в развёрнутом состоянии углы прямые
        if event.type() == QEvent.Type.WindowStateChange:
            self._radius = 0 if self.isMaximized() else 18
            central = self.centralWidget()
            if central is not None:
                central.update()
            if hasattr(self, "hero"):
                self.hero.update()
        super().changeEvent(event)

    def _restore_window_state(self) -> None:
        from utils import user_data_dir

        settings = self.controller.settings
        raw = settings.get("window_geometry") or ""
        maximized = bool(settings.get("window_maximized", True))
        restored = False
        if raw:
            try:
                restored = self.restoreGeometry(base64.b64decode(raw.encode("ascii")))
            except (ValueError, TypeError):
                restored = False
        if not restored:
            self.resize(WIN_W, WIN_H)
            screen = self.screen().availableGeometry() if self.screen() else None
            if screen is not None:
                self.move(screen.center().x() - WIN_W // 2, screen.center().y() - WIN_H // 2)
        if maximized:
            self.showMaximized()
            self.titlebar.btn_max.kind = "restore"
            self.titlebar.btn_max.update()

    def _save_window_state(self) -> None:
        settings = self.controller.settings
        settings.set("window_maximized", self.isMaximized())
        try:
            geometry = bytes(self.saveGeometry().toBase64()).decode("ascii")
            settings.set("window_geometry", geometry)
        except Exception:  # noqa: BLE001
            pass
        settings.save()

    def closeEvent(self, event) -> None:
        self._save_window_state()
        super().closeEvent(event)

    # ------------------------------------------------ Win32: размеры/тень
    WM_NCHITTEST = 0x0084
    WM_GETMINMAXINFO = 0x0024
    WM_LBUTTONDOWN = 0x0201
    WM_LBUTTONUP = 0x0202
    WM_NCLBUTTONDOWN = 0x00A1
    WM_NCLBUTTONUP = 0x00A2
    HTLEFT, HTRIGHT, HTTOP, HTTOPLEFT, HTTOPRIGHT = 10, 11, 12, 13, 14
    HTBOTTOM, HTBOTTOMLEFT, HTBOTTOMRIGHT, HTCLIENT = 15, 16, 17, 1

    class _MINMAXINFO(ctypes.Structure):
        _fields_ = [
            ("ptReserved", wintypes.POINT),
            ("ptMaxSize", wintypes.POINT),
            ("ptMaxPosition", wintypes.POINT),
            ("ptMinTrackSize", wintypes.POINT),
            ("ptMaxTrackSize", wintypes.POINT),
        ]

    class _MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    def nativeEvent(self, event_type, message):
        if self.classic or sys.platform != "win32":
            return super().nativeEvent(event_type, message)
        try:
            if event_type in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == self.WM_GETMINMAXINFO:
                    return self._handle_minmax(msg)
                # Края окна — только изменение размера (без HTCAPTION).
                if msg.message == self.WM_NCHITTEST and not self.isMaximized():
                    return self._handle_hit_test(msg)
                # Кнопки окна обрабатываем по системному курсору: так на них
                # не влияет смещение координат безрамочного окна.
                if msg.message in (self.WM_LBUTTONDOWN, self.WM_NCLBUTTONDOWN):
                    name = self._button_under_cursor(msg.hwnd)
                    self._pressed_button = name
                    if name is not None:
                        return True, 0
                if msg.message in (self.WM_LBUTTONUP, self.WM_NCLBUTTONUP):
                    name = self._button_under_cursor(msg.hwnd)
                    pressed, self._pressed_button = self._pressed_button, None
                    if name is not None and name == pressed:
                        self._run_window_action(name)
                        return True, 0
        except Exception:  # noqa: BLE001 - при любой ошибке работает обычный путь Qt
            pass
        return super().nativeEvent(event_type, message)

    def _button_under_cursor(self, hwnd) -> str | None:
        """Кнопка окна под системным курсором.

        Сначала проверяем точные прямоугольники кнопок в клиентских координатах,
        затем — грубые зоны, посчитанные от системного прямоугольника окна.
        Второй способ не зависит от смещения клиентской области.
        """
        point = wintypes.POINT()
        if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
            return None

        scale = self.devicePixelRatioF() or 1.0
        client = wintypes.POINT(point.x, point.y)
        ctypes.windll.user32.ScreenToClient(wintypes.HWND(int(hwnd)), ctypes.byref(client))

        for pos in (QPoint(int(client.x / scale), int(client.y / scale)),
                    QPoint(client.x, client.y)):
            for name, button in (("min", self.titlebar.btn_min),
                                 ("max", self.titlebar.btn_max),
                                 ("close", self.titlebar.btn_close)):
                origin = button.mapTo(self, QPoint(0, 0))
                rect = QRect(origin, button.size()).adjusted(-4, -4, 4, 4)
                if rect.contains(pos):
                    return name

        # грубые зоны от правого верхнего угла окна на экране
        window_rect = wintypes.RECT()
        if not ctypes.windll.user32.GetWindowRect(wintypes.HWND(int(hwnd)),
                                                  ctypes.byref(window_rect)):
            return None
        from_right = window_rect.right - point.x
        from_top = point.y - window_rect.top
        if from_top < 0 or from_top > 84:
            return None
        LOG.debug("window zone: from_top=%s from_right=%s", from_top, from_right)
        if 6 <= from_right <= 66:
            return "close"
        if 66 < from_right <= 124:
            return "max"
        if 124 < from_right <= 186:
            return "min"
        return None

    def _run_window_action(self, name: str) -> None:
        LOG.info("window control: %s", name)
        if name == "min":
            self.showMinimized()
        elif name == "max":
            self.toggle_maximized()
        elif name == "close":
            self.close()

    def _handle_minmax(self, msg):
        info = self._MINMAXINFO.from_address(msg.lParam)
        monitor = ctypes.windll.user32.MonitorFromWindow(wintypes.HWND(int(msg.hwnd)), 2)
        mon_info = self._MONITORINFO()
        mon_info.cbSize = ctypes.sizeof(self._MONITORINFO)
        if not ctypes.windll.user32.GetMonitorInfoW(monitor, ctypes.byref(mon_info)):
            return False, 0
        work, full = mon_info.rcWork, mon_info.rcMonitor
        info.ptMaxPosition.x = work.left - full.left
        info.ptMaxPosition.y = work.top - full.top
        info.ptMaxSize.x = work.right - work.left
        info.ptMaxSize.y = work.bottom - work.top
        info.ptMaxTrackSize.x = work.right - work.left
        info.ptMaxTrackSize.y = work.bottom - work.top
        return True, 0

    def _handle_hit_test(self, msg):
        """Отдаёт Windows только края окна — для изменения размера.

        Возвращать HTCAPTION для заголовка нельзя: Windows начинает системное
        перетаскивание, и клики по кнопкам «свернуть/развернуть/закрыть» до них
        не доходят. Перетаскивание делает TitleBar через startSystemMove.
        """
        x = ctypes.c_short(msg.lParam & 0xFFFF).value
        y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
        pos = self.mapFromGlobal(QPoint(x, y))
        border = 6
        width, height = self.width(), self.height()
        left = pos.x() <= border
        right = pos.x() >= width - border
        top = pos.y() <= border
        bottom = pos.y() >= height - border

        if left and top:
            return True, self.HTTOPLEFT
        if right and top:
            return True, self.HTTOPRIGHT
        if left and bottom:
            return True, self.HTBOTTOMLEFT
        if right and bottom:
            return True, self.HTBOTTOMRIGHT
        if left:
            return True, self.HTLEFT
        if right:
            return True, self.HTRIGHT
        if top:
            return True, self.HTTOP
        if bottom:
            return True, self.HTBOTTOM
        return False, 0
