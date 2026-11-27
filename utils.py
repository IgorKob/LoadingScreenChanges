"""Общие утилиты: пути, логирование, атомарная запись, хеши."""
from __future__ import annotations

import hashlib
import logging
import os
import sys
import time
from pathlib import Path

APP_NAME = "BlitzCustom"
APP_VERSION = "0.4"
LOG = logging.getLogger("blitz")

_data_dir_cache: Path | None = None


def app_dir() -> Path:
    """Папка, рядом с которой лежит exe (или исходники)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def assets_dir() -> Path:
    """Папка с картинками интерфейса.

    В собранном onefile-EXE ресурсы лежат во временной папке распаковки,
    а рядом с exe их может не быть — проверяем оба места.
    """
    if getattr(sys, "frozen", False):
        near = Path(sys.executable).resolve().parent / "assets"
        if near.is_dir():
            return near
        bundled = getattr(sys, "_MEIPASS", None)
        if bundled:
            return Path(bundled) / "assets"
        return near
    return Path(__file__).resolve().parent / "assets"


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def user_data_dir() -> Path:
    """Папка пользовательских данных (изображения, резервные копии, логи, настройки).

    У установленной программы данные лежат в %LOCALAPPDATA%\\BlitzCustom —
    они переживают удаление приложения и обновления. Если рядом с exe есть файл
    portable.txt, данные хранятся рядом с программой (портативный режим).
    При запуске из исходников данные лежат рядом с кодом.
    """
    global _data_dir_cache
    if _data_dir_cache is not None:
        return _data_dir_cache
    base = app_dir()
    portable = (base / "portable.txt").is_file()
    if getattr(sys, "frozen", False) and not portable:
        local = os.environ.get("LOCALAPPDATA") or str(Path.home())
        target = Path(local) / "BlitzCustom"
        try:
            target.mkdir(parents=True, exist_ok=True)
            _data_dir_cache = target
            return target
        except OSError:
            pass
    if _writable(base):
        _data_dir_cache = base
    else:
        local = os.environ.get("LOCALAPPDATA") or str(Path.home())
        fallback = Path(local) / "BlitzLoadingChanger"
        fallback.mkdir(parents=True, exist_ok=True)
        _data_dir_cache = fallback
    return _data_dir_cache


def subdir(name: str) -> Path:
    path = user_data_dir() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def setup_logging() -> Path:
    """Логи в logs/, файл на каждый запуск + очистка старых."""
    log_dir = subdir("logs")
    stamp = time.strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"blitz_{stamp}.log"

    LOG.setLevel(logging.DEBUG)
    LOG.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S")

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    LOG.addHandler(fh)

    if sys.stdout is not None:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        LOG.addHandler(sh)

    # Чистим логи старше 30 дней
    try:
        cutoff = time.time() - 30 * 86400
        for old in log_dir.glob("blitz_*.log"):
            if old.stat().st_mtime < cutoff:
                old.unlink(missing_ok=True)
    except OSError:
        pass

    LOG.info("=== %s v%s ===", APP_NAME, APP_VERSION)
    return log_file


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Запись через временный файл в той же папке + os.replace."""
    tmp = path.with_name(path.name + ".blc_tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if value < 1024 or unit == "ГБ":
            if unit == "Б":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} ГБ"


def human_time(ts: float) -> str:
    return time.strftime("%d.%m.%Y %H:%M", time.localtime(ts))


INVALID_FILENAME_CHARS = '<>:"/\\|?*'


def safe_filename(text: str) -> str:
    """Имя, допустимое в Windows: без : / \\ и прочих запрещённых символов."""
    cleaned = "".join("_" if ch in INVALID_FILENAME_CHARS or ord(ch) < 32 else ch
                      for ch in str(text))
    cleaned = cleaned.strip(" .")
    return cleaned or "item"
