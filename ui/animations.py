"""Система анимаций: длительности, плавность и глобальные переключатели.

По ТЗ (раздел 9) все переходы короткие (90–280 мс), с плавным ускорением и
замедлением, без блокировки интерфейса. Пользователь может уменьшить или
полностью отключить анимации в настройках.
"""
from __future__ import annotations

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPropertyAnimation,
    QTimer,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

# Режимы из настроек
MODE_FULL = "full"
MODE_REDUCED = "reduced"
MODE_OFF = "off"

# Длительности из ТЗ, мс
DURATION_PAGE = 220
DURATION_CARD = 200
DURATION_HOVER = 140
DURATION_PRESS = 110
DURATION_TOAST = 220

_EASING = QEasingCurve.Type.OutCubic
_EASING_SOFT = QEasingCurve.Type.InOutQuad


class Motion:
    """Глобальные настройки движения: масштаб длительностей и вкл/выкл."""

    def __init__(self) -> None:
        self.mode = MODE_FULL

    def set_mode(self, mode: str) -> None:
        self.mode = mode if mode in (MODE_FULL, MODE_REDUCED, MODE_OFF) else MODE_FULL

    @property
    def enabled(self) -> bool:
        return self.mode != MODE_OFF

    @property
    def scale(self) -> float:
        if self.mode == MODE_OFF:
            return 0.0
        return 0.5 if self.mode == MODE_REDUCED else 1.0

    def duration(self, base: int) -> int:
        """Длительность с поправкой на режим. 0 означает «сразу»."""
        return int(base * self.scale)


MOTION = Motion()


def fade_in(widget: QWidget, duration: int = DURATION_CARD, delay: int = 0) -> None:
    """Плавное появление виджета. Без анимаций — мгновенно видимый.

    По завершении эффект прозрачности снимается: иначе каждая перерисовка
    виджета идёт через offscreen-буфер и интерфейс начинает тормозить.
    """
    ms = MOTION.duration(duration)
    if ms <= 0:
        widget.setGraphicsEffect(None)
        widget.setVisible(True)
        return
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(_EASING)

    def _done() -> None:
        widget.setGraphicsEffect(None)

    anim.finished.connect(_done)
    widget._fade_anim = anim  # держим ссылку, иначе анимацию соберёт GC

    if delay > 0:
        QTimer.singleShot(delay, lambda: _start(anim))
    else:
        _start(anim)


def fade_out(widget: QWidget, duration: int = DURATION_CARD, on_done=None) -> None:
    """Плавное исчезновение. По завершении снимает эффект и вызывает on_done."""
    ms = MOTION.duration(duration)
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
    if ms <= 0:
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(None)
        if on_done:
            on_done()
        return
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(effect.opacity())
    anim.setEndValue(0.0)
    anim.setEasingCurve(_EASING_SOFT)

    def _done() -> None:
        widget.setGraphicsEffect(None)
        if on_done:
            on_done()

    anim.finished.connect(_done)
    widget._fade_anim = anim
    _start(anim)


def animate_value(owner: QWidget, prop: bytes, start: float, end: float,
                  duration: int, *, easing: QEasingCurve.Type = _EASING) -> None:
    """Анимирует числовое свойство виджета, которое он использует в paintEvent."""
    ms = MOTION.duration(duration)
    if ms <= 0:
        _set_prop(owner, prop, end)
        return
    anim = QPropertyAnimation(owner, prop, owner)
    anim.setDuration(ms)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(easing)
    keep = getattr(owner, "_value_anims", None)
    if keep is None:
        keep = {}
        owner._value_anims = keep
    anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
    keep[prop] = anim


def _set_prop(owner: QWidget, prop: bytes, value: float) -> None:
    setter = bytes(prop).decode()
    setter = "set_" + "".join(part.capitalize() for part in setter.split("_"))
    fn = getattr(owner, setter, None)
    if fn is not None:
        fn(value)


def _start(anim: QPropertyAnimation) -> None:
    anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
