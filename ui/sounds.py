"""Тихие звуки интерфейса.

Сигналы синтезируются в WAV при первом запуске (никаких внешних файлов) и
проигрываются через QSoundEffect. Звук можно выключить в настройках.
"""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import utils

SAMPLE_RATE = 44100

_effects: dict[str, object] = {}
_enabled = True
_ready = False


def _synth(path: Path, tones: list[tuple[float, float]], volume: float = 0.16) -> None:
    """Записывает короткий сигнал: список (частота, длительность) идёт по очереди."""
    frames = bytearray()
    for frequency, duration in tones:
        count = int(SAMPLE_RATE * duration)
        for index in range(count):
            # плавная огибающая: быстрая атака и мягкое затухание
            progress = index / count
            envelope = math.sin(progress * math.pi) ** 1.5
            value = math.sin(2 * math.pi * frequency * index / SAMPLE_RATE)
            frames += struct.pack("<h", int(value * envelope * volume * 32767))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(bytes(frames))


def _ensure_files() -> dict[str, Path]:
    folder = utils.user_data_dir() / "sounds"
    folder.mkdir(parents=True, exist_ok=True)
    files = {
        "click": folder / "click.wav",
        "apply": folder / "apply.wav",
        "toggle": folder / "toggle.wav",
        "success": folder / "success.wav",
        "error": folder / "error.wav",
    }
    if not files["click"].exists():
        _synth(files["click"], [(1180.0, 0.018), (880.0, 0.030)], volume=0.13)
    if not files["apply"].exists():
        _synth(files["apply"], [(523.25, 0.045), (659.25, 0.045), (783.99, 0.075)], volume=0.12)
    if not files["toggle"].exists():
        _synth(files["toggle"], [(740.0, 0.020), (988.0, 0.028)], volume=0.10)
    if not files["success"].exists():
        # восходящее трезвучие — «всё получилось»
        _synth(files["success"], [(659.25, 0.05), (783.99, 0.05), (1046.5, 0.11)], volume=0.14)
    if not files["error"].exists():
        # нисходящий мягкий сигнал — «не получилось», без резкости
        _synth(files["error"], [(440.0, 0.08), (329.63, 0.13)], volume=0.13)
    return files


def configure(enabled: bool) -> None:
    """Включает или выключает звуки (значение приходит из настроек)."""
    global _enabled
    _enabled = bool(enabled)


def play(name: str) -> None:
    """Проигрывает короткий сигнал; молча ничего не делает, если звук выключен."""
    if not _enabled:
        return
    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtMultimedia import QSoundEffect
    except ImportError:
        return
    global _ready
    try:
        effect = _effects.get(name)
        if effect is None:
            files = _ensure_files()
            path = files.get(name)
            if path is None:
                return
            effect = QSoundEffect()
            effect.setSource(QUrl.fromLocalFile(str(path)))
            effect.setVolume(0.55)
            _effects[name] = effect
            _ready = True
        effect.play()
    except Exception:
        # звук — необязательная часть: любые сбои не должны ломать интерфейс
        return
