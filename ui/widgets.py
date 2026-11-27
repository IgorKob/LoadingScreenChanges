"""Базовые «стеклянные» элементы интерфейса Dark Pearl Glass.

Всё рисуется вручную через QPainter: полупрозрачные панели, тонкие светящиеся
контуры, перламутровые градиенты и мягкие анимации наведения/нажатия.
"""
from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QPropertyAnimation,
    Property,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QFontMetricsF,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QGraphicsDropShadowEffect,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .animations import (
    DURATION_HOVER,
    DURATION_PRESS,
    MOTION,
    animate_value,
)


# --------------------------------------------------------------------------
# низкоуровневая отрисовка
# --------------------------------------------------------------------------
def rounded_path(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def _lerp(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
        int(a.alpha() + (b.alpha() - a.alpha()) * t),
    )


def _with_alpha(color: QColor, alpha: int) -> QColor:
    c = QColor(color)
    c.setAlpha(alpha)
    return c


def paint_gradient_text(painter: QPainter, rect: QRectF, text: str, font: QFont,
                        start: QColor, end: QColor, *, glow: QColor | None = None,
                        align_center: bool = True) -> None:
    """Рисует текст с градиентной заливкой и мягким свечением (как логотип)."""
    painter.setFont(font)
    metrics = QFontMetricsF(font)
    width = metrics.horizontalAdvance(text)
    height = metrics.ascent() + metrics.descent()
    if align_center:
        x = rect.center().x() - width / 2
    else:
        x = rect.x()
    top = rect.center().y() - height / 2
    baseline = top + metrics.ascent()

    path = QPainterPath()
    path.addText(QPointF(x, baseline), font, text)
    bounds = path.boundingRect()

    if glow is not None:
        pen = QPen(_with_alpha(glow, 70), 10)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        pen.setColor(_with_alpha(glow, 110))
        pen.setWidthF(4.5)
        painter.setPen(pen)
        painter.drawPath(path)

    gradient = QLinearGradient(bounds.topLeft(), bounds.bottomRight())
    gradient.setColorAt(0.0, start)
    gradient.setColorAt(0.55, QColor(start).lighter(112))
    gradient.setColorAt(1.0, end)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.fillPath(path, QBrush(gradient))


# --------------------------------------------------------------------------
# иконки (рисуются векторно, без внешних файлов)
# --------------------------------------------------------------------------
def draw_icon(painter: QPainter, kind: str, rect: QRectF, color: QColor,
              width: float = 1.6) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    cx, cy = x + w / 2, y + h / 2

    if kind == "home":
        path = QPainterPath()
        path.moveTo(x + w * 0.12, cy)
        path.lineTo(cx, y + h * 0.14)
        path.lineTo(x + w * 0.88, cy)
        painter.drawPath(path)
        painter.drawLine(QPointF(x + w * 0.22, cy), QPointF(x + w * 0.22, y + h * 0.86))
        painter.drawLine(QPointF(x + w * 0.78, cy), QPointF(x + w * 0.78, y + h * 0.86))
        painter.drawLine(QPointF(x + w * 0.22, y + h * 0.86), QPointF(x + w * 0.78, y + h * 0.86))
    elif kind == "map":
        path = QPainterPath()
        path.moveTo(x + w * 0.10, y + h * 0.26)
        path.lineTo(x + w * 0.36, y + h * 0.14)
        path.lineTo(x + w * 0.64, y + h * 0.30)
        path.lineTo(x + w * 0.90, y + h * 0.18)
        path.lineTo(x + w * 0.90, y + h * 0.74)
        path.lineTo(x + w * 0.64, y + h * 0.86)
        path.lineTo(x + w * 0.36, y + h * 0.70)
        path.lineTo(x + w * 0.10, y + h * 0.82)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(x + w * 0.36, y + h * 0.14), QPointF(x + w * 0.36, y + h * 0.70))
        painter.drawLine(QPointF(x + w * 0.64, y + h * 0.30), QPointF(x + w * 0.64, y + h * 0.86))
    elif kind == "garage":
        painter.drawLine(QPointF(x + w * 0.08, y + h * 0.72), QPointF(x + w * 0.30, y + h * 0.72))
        path = QPainterPath()
        path.moveTo(x + w * 0.30, y + h * 0.72)
        path.lineTo(x + w * 0.38, y + h * 0.42)
        path.lineTo(x + w * 0.62, y + h * 0.42)
        path.lineTo(x + w * 0.70, y + h * 0.72)
        painter.drawPath(path)
        painter.drawLine(QPointF(x + w * 0.70, y + h * 0.72), QPointF(x + w * 0.92, y + h * 0.72))
        painter.drawEllipse(QPointF(x + w * 0.40, y + h * 0.80), w * 0.07, w * 0.07)
        painter.drawEllipse(QPointF(x + w * 0.62, y + h * 0.80), w * 0.07, w * 0.07)
    elif kind == "image":
        box = QRectF(x + w * 0.12, y + h * 0.18, w * 0.76, h * 0.64)
        painter.drawRoundedRect(box, w * 0.10, w * 0.10)
        painter.drawEllipse(QPointF(x + w * 0.34, y + h * 0.38), w * 0.06, w * 0.06)
        path = QPainterPath()
        path.moveTo(x + w * 0.18, y + h * 0.76)
        path.lineTo(x + w * 0.40, y + h * 0.52)
        path.lineTo(x + w * 0.56, y + h * 0.68)
        path.lineTo(x + w * 0.68, y + h * 0.56)
        path.lineTo(x + w * 0.82, y + h * 0.76)
        painter.drawPath(path)
    elif kind == "shield":
        path = QPainterPath()
        path.moveTo(cx, y + h * 0.10)
        path.lineTo(x + w * 0.86, y + h * 0.26)
        path.lineTo(x + w * 0.86, y + h * 0.54)
        path.cubicTo(x + w * 0.86, y + h * 0.78, cx, y + h * 0.90, cx, y + h * 0.90)
        path.cubicTo(cx, y + h * 0.90, x + w * 0.14, y + h * 0.78, x + w * 0.14, y + h * 0.54)
        path.lineTo(x + w * 0.14, y + h * 0.26)
        path.closeSubpath()
        painter.drawPath(path)
    elif kind == "clock":
        painter.drawEllipse(QPointF(cx, cy), w * 0.36, w * 0.36)
        painter.drawLine(QPointF(cx, cy), QPointF(cx, y + h * 0.30))
        painter.drawLine(QPointF(cx, cy), QPointF(x + w * 0.66, cy + h * 0.10))
    elif kind == "gear":
        painter.drawEllipse(QPointF(cx, cy), w * 0.16, w * 0.16)
        painter.drawEllipse(QPointF(cx, cy), w * 0.33, w * 0.33)
        for i in range(8):
            import math
            angle = math.radians(i * 45)
            import math as _m
            p1 = QPointF(cx + _m.cos(angle) * w * 0.33, cy + _m.sin(angle) * h * 0.33)
            p2 = QPointF(cx + _m.cos(angle) * w * 0.45, cy + _m.sin(angle) * h * 0.45)
            painter.drawLine(p1, p2)
    elif kind == "info":
        painter.drawEllipse(QPointF(cx, cy), w * 0.38, w * 0.38)
        painter.drawLine(QPointF(cx, y + h * 0.52), QPointF(cx, y + h * 0.70))
        painter.drawPoint(QPointF(cx, y + h * 0.36))
    elif kind == "check":
        path = QPainterPath()
        path.moveTo(x + w * 0.22, cy)
        path.lineTo(x + w * 0.42, y + h * 0.70)
        path.lineTo(x + w * 0.80, y + h * 0.28)
        painter.drawPath(path)
    elif kind == "refresh":
        painter.drawArc(QRectF(x + w * 0.16, y + h * 0.16, w * 0.68, h * 0.68),
                        int(60 * 16), int(260 * 16))
        path = QPainterPath()
        path.moveTo(x + w * 0.72, y + h * 0.10)
        path.lineTo(x + w * 0.86, y + h * 0.26)
        path.lineTo(x + w * 0.66, y + h * 0.32)
        painter.drawPath(path)
    elif kind == "play":
        path = QPainterPath()
        path.moveTo(x + w * 0.34, y + h * 0.22)
        path.lineTo(x + w * 0.80, cy)
        path.lineTo(x + w * 0.34, y + h * 0.78)
        path.closeSubpath()
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)
    elif kind == "search":
        painter.drawEllipse(QPointF(x + w * 0.44, y + h * 0.44), w * 0.26, h * 0.26)
        painter.drawLine(QPointF(x + w * 0.64, y + h * 0.64), QPointF(x + w * 0.84, y + h * 0.84))
    elif kind == "pencil":
        path = QPainterPath()
        path.moveTo(x + w * 0.22, y + h * 0.78)
        path.lineTo(x + w * 0.30, y + h * 0.54)
        path.lineTo(x + w * 0.72, y + h * 0.12)
        path.lineTo(x + w * 0.88, y + h * 0.28)
        path.lineTo(x + w * 0.46, y + h * 0.70)
        path.closeSubpath()
        painter.drawPath(path)
    elif kind == "close":
        painter.drawLine(QPointF(x + w * 0.28, y + h * 0.28), QPointF(x + w * 0.72, y + h * 0.72))
        painter.drawLine(QPointF(x + w * 0.72, y + h * 0.28), QPointF(x + w * 0.28, y + h * 0.72))
    elif kind == "minimize":
        painter.drawLine(QPointF(x + w * 0.26, cy), QPointF(x + w * 0.74, cy))
    elif kind == "maximize":
        painter.drawRoundedRect(QRectF(x + w * 0.28, y + h * 0.28, w * 0.44, h * 0.44), 2, 2)
    elif kind == "restore":
        painter.drawRoundedRect(QRectF(x + w * 0.26, y + h * 0.34, w * 0.40, h * 0.40), 2, 2)
        painter.drawRoundedRect(QRectF(x + w * 0.36, y + h * 0.24, w * 0.40, h * 0.40), 2, 2)
    elif kind == "folder":
        path = QPainterPath()
        path.moveTo(x + w * 0.14, y + h * 0.30)
        path.lineTo(x + w * 0.42, y + h * 0.30)
        path.lineTo(x + w * 0.50, y + h * 0.40)
        path.lineTo(x + w * 0.86, y + h * 0.40)
        path.lineTo(x + w * 0.86, y + h * 0.74)
        path.lineTo(x + w * 0.14, y + h * 0.74)
        path.closeSubpath()
        painter.drawPath(path)
    elif kind == "arrow_right":
        painter.drawLine(QPointF(x + w * 0.24, cy), QPointF(x + w * 0.76, cy))
        path = QPainterPath()
        path.moveTo(x + w * 0.56, cy - h * 0.16)
        path.lineTo(x + w * 0.76, cy)
        path.lineTo(x + w * 0.56, cy + h * 0.16)
        painter.drawPath(path)
    elif kind == "trash":
        painter.drawLine(QPointF(x + w * 0.18, y + h * 0.28), QPointF(x + w * 0.82, y + h * 0.28))
        painter.drawLine(QPointF(x + w * 0.40, y + h * 0.18), QPointF(x + w * 0.60, y + h * 0.18))
        path = QPainterPath()
        path.moveTo(x + w * 0.26, y + h * 0.32)
        path.lineTo(x + w * 0.32, y + h * 0.84)
        path.lineTo(x + w * 0.68, y + h * 0.84)
        path.lineTo(x + w * 0.74, y + h * 0.32)
        painter.drawPath(path)
    elif kind == "warn":
        path = QPainterPath()
        path.moveTo(cx, y + h * 0.14)
        path.lineTo(x + w * 0.88, y + h * 0.82)
        path.lineTo(x + w * 0.12, y + h * 0.82)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(cx, y + h * 0.38), QPointF(cx, y + h * 0.60))
        painter.drawPoint(QPointF(cx, y + h * 0.71))
    elif kind == "grid":
        for dx in (0.14, 0.52):
            for dy in (0.14, 0.52):
                painter.drawRoundedRect(
                    QRectF(x + w * dx, y + h * dy, w * 0.32, h * 0.32), 2.5, 2.5)
    elif kind == "spark":
        path = QPainterPath()
        path.moveTo(cx, y + h * 0.08)
        path.cubicTo(cx + w * 0.06, y + h * 0.36, x + w * 0.64, y + h * 0.44, x + w * 0.92, cy)
        path.cubicTo(x + w * 0.64, cy + h * 0.06, cx + w * 0.06, y + h * 0.64, cx, y + h * 0.92)
        path.cubicTo(cx - w * 0.06, y + h * 0.64, x + w * 0.36, cy + h * 0.06, x + w * 0.08, cy)
        path.cubicTo(x + w * 0.36, y + h * 0.44, cx - w * 0.06, y + h * 0.36, cx, y + h * 0.08)
        painter.drawPath(path)
    painter.restore()


# --------------------------------------------------------------------------
# панели
# --------------------------------------------------------------------------
class GlassPanel(QWidget):
    """Полупрозрачная панель со скруглением, тонким контуром и подсветкой."""

    clicked = Signal()

    def __init__(self, parent=None, *, radius: int = theme.RADIUS_PANEL,
                 fill: QColor | None = None, border: QColor | None = None,
                 hoverable: bool = False, glow: QColor | None = None):
        super().__init__(parent)
        self.radius = radius
        self._fill = fill or theme.PANEL_FILL
        self._border = border or theme.PANEL_BORDER
        self._hoverable = hoverable
        self._hover_t = 0.0
        self._active = False
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        if glow is not None:
            self.set_glow(glow)

    # анимируемое свойство наведения
    def _get_hover(self) -> float:
        return self._hover_t

    def _set_hover(self, value: float) -> None:
        self._hover_t = value
        self.update()

    hover_t = Property(float, _get_hover, _set_hover)

    def set_glow(self, color: QColor, blur: int = 34) -> None:
        effect = QGraphicsDropShadowEffect(self)
        effect.setBlurRadius(blur)
        effect.setOffset(0, 4)
        c = QColor(color)
        c.setAlpha(90)
        effect.setColor(c)
        self.setGraphicsEffect(effect)

    def set_active(self, active: bool) -> None:
        self._active = active
        self.update()

    def enterEvent(self, event) -> None:
        if self._hoverable:
            animate_value(self, b"hover_t", self._hover_t, 1.0, DURATION_HOVER)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if self._hoverable:
            animate_value(self, b"hover_t", self._hover_t, 0.0, DURATION_HOVER)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = rounded_path(rect, self.radius)

        fill = _lerp(self._fill, theme.PANEL_FILL_HOVER, self._hover_t)
        if self._active:
            fill = _lerp(fill, theme.PANEL_FILL_ACTIVE, 0.65)
        painter.fillPath(path, fill)

        # перламутровый перелив сверху вниз
        pearl = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        pearl.setColorAt(0.0, QColor(255, 255, 255, 26))
        pearl.setColorAt(0.45, QColor(255, 255, 255, 6))
        pearl.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillPath(path, QBrush(pearl))

        painter.save()
        painter.setClipPath(path)
        # блик по верхней кромке — «толщина стекла»
        edge = QLinearGradient(rect.topLeft(), rect.topRight())
        edge.setColorAt(0.0, QColor(255, 255, 255, 0))
        edge.setColorAt(0.18, QColor(255, 255, 255, 96))
        edge.setColorAt(0.5, QColor(255, 255, 255, 130))
        edge.setColorAt(0.82, QColor(255, 255, 255, 96))
        edge.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(QPen(QBrush(edge), 1.2))
        painter.drawLine(QPointF(rect.left() + 6, rect.top() + 1),
                         QPointF(rect.right() - 6, rect.top() + 1))

        # мягкая внутренняя тень у нижней кромки
        shade = QLinearGradient(rect.bottomLeft(), rect.bottomLeft() - QPoint(0, 30))
        shade.setColorAt(0.0, QColor(0, 0, 0, 46))
        shade.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(QRectF(rect.x(), rect.bottom() - 30, rect.width(), 30), shade)

        # блик в левом верхнем углу
        sheen = QRadialGradient(rect.left() + rect.width() * 0.12, rect.top() + 4,
                                max(rect.width() * 0.5, 80))
        sheen.setColorAt(0.0, QColor(255, 255, 255, 22))
        sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(rect, sheen)
        painter.restore()

        border = _lerp(self._border, theme.PANEL_BORDER_ACTIVE, self._hover_t)
        if self._active:
            border = _lerp(border, theme.PANEL_BORDER_ACTIVE, 0.8)
        frame = QLinearGradient(rect.topLeft(), rect.bottomRight())
        frame.setColorAt(0.0, _with_alpha(border, min(255, border.alpha() + 40)))
        frame.setColorAt(1.0, _with_alpha(border, max(0, border.alpha() - 14)))
        painter.setPen(QPen(QBrush(frame), 1.0))
        painter.drawPath(path)
        painter.end()


# --------------------------------------------------------------------------
# кнопки
# --------------------------------------------------------------------------
class IconButton(QAbstractButton):
    """Круглая кнопка с векторной иконкой."""

    def __init__(self, kind: str, parent=None, *, size: int = 34,
                 hover_color: QColor | None = None, icon_color: QColor | None = None,
                 tooltip: str = ""):
        super().__init__(parent)
        self.kind = kind
        self._size = size
        self._hover_color = hover_color or theme.PANEL_FILL_HOVER
        self._icon_color = icon_color or theme.TEXT_DIM
        self._hover_t = 0.0
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def _get_hover(self) -> float:
        return self._hover_t

    def _set_hover(self, value: float) -> None:
        self._hover_t = value
        self.update()

    hover_t = Property(float, _get_hover, _set_hover)

    def enterEvent(self, event) -> None:
        animate_value(self, b"hover_t", self._hover_t, 1.0, DURATION_HOVER)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        animate_value(self, b"hover_t", self._hover_t, 0.0, DURATION_HOVER)
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self._hover_t > 0.01 or self.isDown():
            fill = _with_alpha(self._hover_color, int(90 + 60 * self._hover_t))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, self._size / 2, self._size / 2)
        color = _lerp(self._icon_color, theme.TEXT, self._hover_t)
        if self.isDown():
            color = theme.ACCENT_LIGHT
        margin = self._size * 0.28
        draw_icon(painter, self.kind, QRectF(rect).adjusted(margin, margin, -margin, -margin), color, 1.5)
        painter.end()


class GhostButton(QAbstractButton):
    """Кнопка-контур с иконкой и текстом."""

    def __init__(self, text: str, parent=None, *, icon: str = "",
                 height: int = 40, min_width: int = 0):
        super().__init__(parent)
        self.setText(text)
        self.icon_kind = icon
        self._hover_t = 0.0
        self.setMinimumHeight(height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        fm = QFontMetrics(theme.font(10, QFont.Weight.Medium))
        need = fm.horizontalAdvance(text) + (34 if icon else 26) + 24
        self.setMinimumWidth(max(min_width, need))
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

    def _get_hover(self) -> float:
        return self._hover_t

    def _set_hover(self, value: float) -> None:
        self._hover_t = value
        self.update()

    hover_t = Property(float, _get_hover, _set_hover)

    def enterEvent(self, event) -> None:
        animate_value(self, b"hover_t", self._hover_t, 1.0, DURATION_HOVER)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        animate_value(self, b"hover_t", self._hover_t, 0.0, DURATION_HOVER)
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = rounded_path(rect, theme.RADIUS_BUTTON)
        fill = _lerp(QColor(255, 255, 255, 10), QColor(255, 255, 255, 26), self._hover_t)
        painter.fillPath(path, fill)
        painter.setPen(QPen(_lerp(theme.PANEL_BORDER, theme.PANEL_BORDER_ACTIVE, self._hover_t), 1.0))
        painter.drawPath(path)

        font = theme.font(10, QFont.Weight.Medium)
        painter.setFont(font)
        painter.setPen(_lerp(theme.TEXT_DIM, theme.TEXT, self._hover_t))
        fm = QFontMetrics(font)
        text_w = fm.horizontalAdvance(self.text())
        icon_w = 18 if self.icon_kind else 0
        gap = 8 if self.icon_kind else 0
        total = text_w + icon_w + gap
        start_x = rect.center().x() - total / 2
        if self.icon_kind:
            draw_icon(painter, self.icon_kind,
                      QRectF(start_x, rect.center().y() - 8, 16, 16),
                      _lerp(theme.TEXT_DIM, theme.TEXT, self._hover_t), 1.5)
            start_x += icon_w + gap
        painter.drawText(QRectF(start_x, rect.top(), text_w, rect.height()),
                         int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self.text())
        painter.end()


class AccentButton(QAbstractButton):
    """Основная кнопка с градиентом и состояниями: обычное, работа, успех, ошибка."""

    STATE_IDLE = "idle"
    STATE_BUSY = "busy"
    STATE_SUCCESS = "success"
    STATE_ERROR = "error"

    def __init__(self, text: str, parent=None, *, icon: str = "play", height: int = 46):
        super().__init__(parent)
        self.setText(text)
        self.icon_kind = icon
        self.state = self.STATE_IDLE
        self._hover_t = 0.0
        self._press_t = 0.0
        self._spin = 0.0
        self._msg = ""
        self.setMinimumHeight(height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(33)
        self._spin_timer.timeout.connect(self._on_spin)

    # --- свойства ---
    def _get_hover(self) -> float:
        return self._hover_t

    def _set_hover(self, value: float) -> None:
        self._hover_t = value
        self.update()

    hover_t = Property(float, _get_hover, _set_hover)

    def _get_press(self) -> float:
        return self._press_t

    def _set_press(self, value: float) -> None:
        self._press_t = value
        self.update()

    press_t = Property(float, _get_press, _set_press)

    # --- состояние ---
    def set_state(self, state: str, message: str = "") -> None:
        self.state = state
        self._msg = message
        if state == self.STATE_BUSY:
            self._spin_timer.start()
        else:
            self._spin_timer.stop()
        self.setEnabled(state in (self.STATE_IDLE, self.STATE_ERROR))
        self.update()

    def reset_state(self) -> None:
        self.set_state(self.STATE_IDLE)

    def _on_spin(self) -> None:
        self._spin = (self._spin + 12) % 360
        self.update()

    # --- события ---
    def enterEvent(self, event) -> None:
        if self.isEnabled():
            animate_value(self, b"hover_t", self._hover_t, 1.0, DURATION_HOVER)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        animate_value(self, b"hover_t", self._hover_t, 0.0, DURATION_HOVER)
        animate_value(self, b"press_t", self._press_t, 0.0, DURATION_PRESS)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if self.isEnabled():
            animate_value(self, b"press_t", self._press_t, 1.0, DURATION_PRESS)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        animate_value(self, b"press_t", self._press_t, 0.0, DURATION_PRESS)
        super().mouseReleaseEvent(event)

    # --- отрисовка ---
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self._press_t:
            rect = rect.adjusted(1, 1, -1, -1)
        path = rounded_path(rect, theme.RADIUS_BUTTON)

        if self.state == self.STATE_SUCCESS:
            c1, c2 = QColor("#14B8A6"), QColor("#2DD4BF")
        elif self.state == self.STATE_ERROR:
            c1, c2 = QColor("#B45309"), QColor("#F59E0B")
        elif self.state == self.STATE_BUSY:
            c1, c2 = QColor("#6D28D9"), QColor("#8B5CF6")
        else:
            c1 = _lerp(QColor("#6D28D9"), QColor("#7C3AED"), self._hover_t)
            c2 = _lerp(QColor("#8B5CF6"), QColor("#A78BFA"), self._hover_t)

        if not self.isEnabled():
            c1, c2 = QColor(90, 84, 120, 120), QColor(110, 102, 145, 120)

        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, c1)
        grad.setColorAt(1.0, c2)
        painter.fillPath(path, QBrush(grad))

        # внутренний блик
        glow = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        glow.setColorAt(0.0, QColor(255, 255, 255, 52))
        glow.setColorAt(0.5, QColor(255, 255, 255, 8))
        glow.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillPath(path, QBrush(glow))

        painter.setPen(QPen(QColor(255, 255, 255, 60 + int(60 * self._hover_t)), 1.0))
        painter.drawPath(path)

        font = theme.font(10, QFont.Weight.DemiBold, 0.2)
        painter.setFont(font)
        painter.setPen(QColor("#FFFFFF") if self.isEnabled() else QColor("#CFC9E8"))
        fm = QFontMetrics(font)

        label = self.text()
        if self.state == self.STATE_BUSY:
            label = "Применение…"
        elif self.state == self.STATE_SUCCESS:
            label = "Применено"
        elif self.state == self.STATE_ERROR and self._msg:
            label = self._msg

        text_w = fm.horizontalAdvance(label)
        icon_w = 18 if self.icon_kind else 0
        gap = 10 if self.icon_kind else 0
        total = text_w + icon_w + gap
        x = rect.center().x() - total / 2
        cy = rect.center().y()

        if self.state == self.STATE_BUSY:
            painter.setPen(QPen(QColor("#E9DEFF"), 2.0))
            spinner = QRectF(x, cy - 8, 16, 16)
            painter.drawArc(spinner, int(self._spin * 16), int(240 * 16))
            x += icon_w + gap
        elif self.icon_kind:
            kind = "check" if self.state == self.STATE_SUCCESS else (
                "warn" if self.state == self.STATE_ERROR else self.icon_kind)
            draw_icon(painter, kind, QRectF(x, cy - 8, 16, 16), QColor("#FFFFFF"), 1.8)
            x += icon_w + gap

        painter.drawText(QRectF(x, rect.top(), text_w + 2, rect.height()),
                         int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), label)
        painter.end()


class NavButton(QAbstractButton):
    """Пункт боковой навигации: иконка, подпись, подсветка активного."""

    def __init__(self, key: str, text: str, icon: str, parent=None):
        super().__init__(parent)
        self.key = key
        self.icon_kind = icon
        self.setText(text)
        self._active = False
        self._hover_t = 0.0
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(46)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def _get_hover(self) -> float:
        return self._hover_t

    def _set_hover(self, value: float) -> None:
        self._hover_t = value
        self.update()

    hover_t = Property(float, _get_hover, _set_hover)

    def set_active(self, active: bool) -> None:
        self._active = active
        self.update()

    def enterEvent(self, event) -> None:
        animate_value(self, b"hover_t", self._hover_t, 1.0, DURATION_HOVER)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        animate_value(self, b"hover_t", self._hover_t, 0.0, DURATION_HOVER)
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = rounded_path(rect, 13)

        if self._active:
            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(0.0, QColor(139, 92, 246, 110))
            grad.setColorAt(1.0, QColor(96, 165, 250, 60))
            painter.fillPath(path, QBrush(grad))
            painter.setPen(QPen(QColor(167, 139, 250, 150), 1.0))
            painter.drawPath(path)
        elif self._hover_t > 0.01:
            painter.fillPath(path, _with_alpha(QColor(255, 255, 255, 22), int(60 * self._hover_t)))
            painter.setPen(QPen(_with_alpha(theme.PANEL_BORDER, int(90 * self._hover_t)), 1.0))
            painter.drawPath(path)

        icon_color = theme.TEXT if self._active else _lerp(theme.TEXT_MUTED, theme.TEXT_DIM, self._hover_t)
        draw_icon(painter, self.icon_kind, QRectF(rect.x() + 15, rect.center().y() - 9, 18, 18),
                  icon_color, 1.6)

        font = theme.font(10, QFont.Weight.DemiBold if self._active else QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(theme.TEXT if self._active else _lerp(theme.TEXT_DIM, theme.TEXT, self._hover_t))
        painter.drawText(QRectF(rect.x() + 45, rect.top(), rect.width() - 55, rect.height()),
                         int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self.text())
        painter.end()


# --------------------------------------------------------------------------
# информационные элементы
# --------------------------------------------------------------------------
class StatCard(GlassPanel):
    """Плитка со значением и подписью (как на макете главного экрана)."""

    def __init__(self, icon: str, value: str, caption: str, parent=None,
                 accent: QColor | None = None):
        super().__init__(parent, radius=theme.RADIUS_CARD, hoverable=True)
        self.icon_kind = icon
        self._value = value
        self._caption = caption
        self._accent = accent or theme.ACCENT_LIGHT
        self.setMinimumHeight(86)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_values(self, value: str, caption: str, accent: QColor | None = None) -> None:
        self._value = value
        self._caption = caption
        if accent is not None:
            self._accent = accent
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())

        chip = QRectF(rect.x() + 18, rect.center().y() - 20, 40, 40)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_with_alpha(self._accent, 46))
        painter.drawRoundedRect(chip, 12, 12)
        draw_icon(painter, self.icon_kind, chip.adjusted(11, 11, -11, -11), self._accent, 1.7)

        font_value = theme.font(19, QFont.Weight.DemiBold)
        painter.setFont(font_value)
        painter.setPen(theme.TEXT)
        text_x = chip.right() + 14
        painter.drawText(QRectF(text_x, rect.y() + 16, rect.width() - text_x - 12, 30),
                         int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self._value)

        painter.setFont(theme.font(9, QFont.Weight.Normal))
        painter.setPen(theme.TEXT_DIM)
        painter.drawText(QRectF(text_x, rect.y() + 46, rect.width() - text_x - 12, 24),
                         int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self._caption)
        painter.end()


class Badge(QWidget):
    """Небольшая цветная метка статуса."""

    def __init__(self, text: str, parent=None, color: QColor | None = None):
        super().__init__(parent)
        self._text = text
        self._color = color or theme.TEXT_DIM
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedHeight(22)
        fm = QFontMetrics(theme.font(8, QFont.Weight.Medium))
        self.setFixedWidth(fm.horizontalAdvance(text) + 20)

    def set_state(self, text: str, color: QColor) -> None:
        self._text = text
        self._color = color
        fm = QFontMetrics(theme.font(8, QFont.Weight.Medium))
        self.setFixedWidth(fm.horizontalAdvance(text) + 20)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_with_alpha(self._color, 44))
        painter.drawRoundedRect(rect, 11, 11)
        painter.setFont(theme.font(8, QFont.Weight.Medium))
        painter.setPen(self._color)
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), self._text)
        painter.end()


class Thumb(QWidget):
    """Миниатюра изображения с закруглением и заглушкой."""

    def __init__(self, parent=None, *, radius: int = 12, placeholder: str = "нет изображения"):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._radius = radius
        self._placeholder = placeholder
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(120, 68)

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        rect = QRectF(self.rect())
        path = rounded_path(rect, self._radius)
        painter.setClipPath(path)
        painter.fillPath(path, QColor(255, 255, 255, 10))

        if self._pixmap is not None and not self._pixmap.isNull():
            # шахматка показывает прозрачность игровых текстур
            cell = 8.0
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 10))
            row = 0
            y = rect.top()
            while y < rect.bottom():
                x = rect.left() + (cell if row % 2 else 0)
                while x < rect.right():
                    painter.drawRect(QRectF(x, y, cell, cell))
                    x += cell * 2
                y += cell
                row += 1

            # вписываем целиком, ничего не обрезая
            area = rect.adjusted(6, 6, -6, -6)
            scaled = self._pixmap.scaled(
                area.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            x = area.center().x() - scaled.width() / 2
            y = area.center().y() - scaled.height() / 2
            painter.drawPixmap(int(x), int(y), scaled)
        else:
            painter.setPen(QPen(QColor(255, 255, 255, 18), 1.0))
            painter.drawPath(path)
            draw_icon(painter, "image",
                      QRectF(rect.center().x() - 12, rect.center().y() - 20, 24, 24),
                      QColor(255, 255, 255, 40), 1.4)
            painter.setFont(theme.font(8))
            painter.setPen(QColor(255, 255, 255, 46))
            painter.drawText(QRectF(rect.x(), rect.center().y() + 8, rect.width(), 18),
                             int(Qt.AlignmentFlag.AlignCenter), self._placeholder)

        painter.setClipping(False)
        painter.setPen(QPen(QColor(255, 255, 255, 26), 1.0))
        painter.drawPath(path)
        painter.end()


class Toast(QWidget):
    """Уведомление внутри окна: появляется снизу, плавно исчезает."""

    _active: list["Toast"] = []

    def __init__(self, parent: QWidget, text: str, *, kind: str = "info", timeout: int = 3200):
        super().__init__(parent)
        self._text = text
        self._kind = kind
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        fm = QFontMetrics(theme.font(9, QFont.Weight.Medium))
        width = min(fm.horizontalAdvance(text) + 72, parent.width() - 80)
        self.resize(max(220, width), 44)
        self._position()
        self.show()
        self.raise_()
        from .animations import fade_in as _fade_in

        _fade_in(self, 220)
        QTimer.singleShot(timeout, self._close)
        Toast._active.append(self)

    def _position(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        x = (parent.width() - self.width()) // 2
        y = parent.height() - self.height() - 58
        self.move(x, y)
        self._y = y

    def _close(self) -> None:
        from .animations import fade_out as _fade_out

        _fade_out(self, 200, self._finish)

    def _finish(self) -> None:
        if self in Toast._active:
            Toast._active.remove(self)
        self.hide()
        self.deleteLater()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = rounded_path(rect, 14)
        painter.fillPath(path, QColor(24, 18, 48, 235))
        accent = {"info": theme.ACCENT_LIGHT, "success": theme.TEAL,
                  "error": theme.AMBER}.get(self._kind, theme.ACCENT_LIGHT)
        painter.setPen(QPen(_with_alpha(accent, 150), 1.0))
        painter.drawPath(path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        painter.drawRoundedRect(QRectF(rect.x() + 1, rect.y() + 12, 3, rect.height() - 24), 1.5, 1.5)
        painter.setFont(theme.font(9, QFont.Weight.Medium))
        painter.setPen(theme.TEXT)
        painter.drawText(rect.adjusted(18, 0, -14, 0),
                         int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self._text)
        painter.end()


def header_row(title: str, subtitle: str = "") -> QWidget:
    """Заголовок страницы: крупный текст и пояснение."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    label = QLabel(title)
    label.setFont(theme.font(16, QFont.Weight.DemiBold))
    label.setStyleSheet(f"color: {theme.C_TEXT};")
    layout.addWidget(label)

    if subtitle:
        sub = QLabel(subtitle)
        sub.setFont(theme.font(9))
        sub.setStyleSheet(f"color: {theme.C_TEXT_DIM};")
        sub.setWordWrap(True)
        layout.addWidget(sub)
    return widget
