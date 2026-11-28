"""Связующий слой между интерфейсом и движком приложения.

Здесь собраны все операции, которые нужны страницам: обнаружение игры,
сканирование ресурсов, назначение изображений, применение и восстановление.
Долгие операции выполняются в фоновых потоках, чтобы интерфейс не замирал
(ТЗ, раздел 12).
"""
from __future__ import annotations

import io
import time
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image
from PySide6.QtCore import (QObject, QRunnable, QSize, Qt, QThreadPool, QTimer,
                            Signal)
from PySide6.QtGui import QImage, QPixmap

from backup_manager import BackupError, BackupManager
from game_detector import GameInfo, detect_game
from image_processor import ImageError, copy_user_image, load_game_image, validate_image
from map_database import load_catalog
import resource_catalog
from resource_replacer import ApplyError, apply_map, is_game_running, restore_all, restore_map
from resource_scanner import ScanResult, scan_resources, scan_from_settings
from settings_manager import SettingsManager
from utils import LOG, user_data_dir


class _WorkerSignals(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(int, str)


class _Worker(QRunnable):
    """Выполняет функцию в пуле потоков и сообщает результат сигналом."""

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001 - ошибка уходит в интерфейс
            LOG.exception("Фоновая операция завершилась ошибкой")
            self.signals.failed.emit(str(exc))
            return
        self.signals.done.emit(result)


@dataclass
class Stats:
    """Числа для главной страницы."""

    game_found: bool = False
    game_path: str = ""
    resources_found: int = 0
    resources_total: int = 0
    assigned: int = 0
    pending: int = 0
    errors: int = 0
    backups: int = 0
    last_operations: list[dict] = field(default_factory=list)


INDEX_VERSION = 3


class ThumbCache:
    """Кэш миниатюр: ограничен по количеству, чтобы не держать всё в памяти."""

    def __init__(self, limit: int = 64, size: QSize | None = None):
        self.limit = limit
        self.size = size or QSize(360, 240)
        self._items: dict[str, QPixmap] = {}

    def get(self, key: str, path: str | Path | None) -> QPixmap | None:
        if key in self._items:
            return self._items[key]
        if path is None:
            return None
        pixmap = self._load(Path(path))
        if pixmap is not None:
            if len(self._items) >= self.limit:
                self._items.pop(next(iter(self._items)))
            self._items[key] = pixmap
        return pixmap

    def _load(self, path: Path) -> QPixmap | None:
        if path.name.lower().endswith(".dds.dvpl"):
            return self._load_dds(path)
        try:
            image = load_game_image(path)
            thumb = image.copy()
            thumb.thumbnail((self.size.width(), self.size.height()), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            thumb.convert("RGB").save(buffer, format="PNG")
            qt_image = QImage.fromData(buffer.getvalue(), "PNG")
            return QPixmap.fromImage(qt_image)
        except (ImageError, OSError, ValueError) as exc:
            LOG.warning("Не удалось построить миниатюру %s: %s", path, exc)
            return None

    def _load_dds(self, path: Path) -> QPixmap | None:
        """Камуфляж — текстура DDS: декодируем через texconv и кэшируем PNG."""
        try:
            from camo import thumbnail
            png = thumbnail(path, 0, 0)
            if png is None:
                return None
            image = QImage(str(png))
            if image.isNull():
                return None
            scaled = image.scaled(self.size, Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
            return QPixmap.fromImage(scaled)
        except (OSError, ValueError) as exc:
            LOG.warning("Не удалось построить миниатюру камуфляжа %s: %s", path, exc)
            return None

    def clear(self) -> None:
        self._items.clear()


class AppController(QObject):
    """Единая точка доступа к состоянию приложения для всех страниц."""

    scan_started = Signal()
    scan_finished = Signal()
    detect_finished = Signal()
    images_scanned = Signal()
    assignments_changed = Signal()
    apply_progress = Signal(int, int)
    apply_finished = Signal(object)
    restore_finished = Signal(object)
    toast = Signal(str, str)  # text, kind

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = SettingsManager()
        self.maps: list[dict] = load_catalog(user_data_dir() / "maps.json")
        self.backups = BackupManager(self.settings.backups_dir())
        self.game: GameInfo | None = None
        self.scan: ScanResult = scan_from_settings(self.settings.get("scan") or {})
        self.images: dict[str, dict] = resource_catalog.load_index(
            self.settings.get("image_index") or {})
        # индекс, сохранённый прошлой версией, не знает о новых категориях
        if int(self.settings.get("image_index_version") or 0) != INDEX_VERSION:
            self.images = {}
        self.busy_images = False
        self.thumbs = ThumbCache()
        self.pool = QThreadPool.globalInstance()
        self.busy_scan = False
        self.busy_apply = False
        self.last_apply: dict = {}
        self.history: list[dict] = list(self.settings.get("history") or [])
        self._map_by_code = {item["code"]: item for item in self.maps}

    # ---------------------------------------------------------------- игра
    def detect(self) -> None:
        """Фоновое обнаружение игры с последующим сканированием ресурсов."""
        if self.busy_scan:
            return
        self.busy_scan = True
        self.scan_started.emit()
        worker = _Worker(self._detect_task)
        worker.signals.done.connect(self._on_detected)
        worker.signals.failed.connect(self._on_detect_failed)
        self.pool.start(worker)

    def _detect_task(self) -> tuple[GameInfo, ScanResult | None]:
        info = detect_game(self.settings.get("game_root"), deep_search=True)
        result = None
        if info.loading_root:
            result = scan_resources(info.loading_root, self.maps)
        return info, result

    def _on_detected(self, payload) -> None:
        info, result = payload
        self.game = info
        self.busy_scan = False
        if info.found:
            self.settings.set("game_root", str(info.root))
            self.settings.set("game_version", info.version)
            self.settings.set("detected_source", info.source)
        if result is not None:
            self.scan = result
            self.settings.set("scan", result.to_settings())
        self.settings.save()
        self.detect_finished.emit()
        self.scan_finished.emit()
        # индекс уже сохранён — не тратим минуты на повторный проход
        if not self.images:
            self.scan_images()

    def _on_detect_failed(self, message: str) -> None:
        self.busy_scan = False
        LOG.error("Обнаружение игры не удалось: %s", message)
        self.toast.emit(f"Не удалось найти игру: {message}", "error")
        self.detect_finished.emit()

    def rescan(self) -> None:
        """Повторное сканирование известной папки ресурсов."""
        if self.busy_scan:
            return
        self.busy_scan = True
        self.scan_started.emit()
        loading_root = (self.game.loading_root if self.game else None) or self.settings.get("loading_root")
        worker = _Worker(self._rescan_task, loading_root)
        worker.signals.done.connect(self._on_rescanned)
        worker.signals.failed.connect(self._on_rescan_failed)
        self.pool.start(worker)

    def _rescan_task(self, loading_root):
        if not loading_root:
            raise RuntimeError("Папка ресурсов не определена. Проверьте игру заново.")
        return scan_resources(loading_root, self.maps)

    def _on_rescanned(self, result: ScanResult) -> None:
        self.busy_scan = False
        self.scan = result
        self.settings.set("scan", result.to_settings())
        self.settings.save()
        self.scan_finished.emit()

    def _on_rescan_failed(self, message: str) -> None:
        self.busy_scan = False
        self.toast.emit(message, "error")
        self.scan_finished.emit()

    # ------------------------------------------------- изображения игры
    def scan_images(self) -> None:
        """Фоновое построение индекса игровых изображений по категориям."""
        if self.busy_images:
            return
        data_dir = self.game.data_dir if self.game else None
        if data_dir is None:
            root = self.settings.get("game_root")
            candidate = Path(root) / "Data" if root else None
            data_dir = candidate if candidate is not None and candidate.is_dir() else None
        if data_dir is None:
            return
        self.busy_images = True
        worker = _Worker(self._scan_images_task, data_dir)
        worker.signals.done.connect(self._on_images_scanned)
        worker.signals.failed.connect(self._on_images_failed)
        self.pool.start(worker)

    def _scan_images_task(self, data_dir) -> list[dict]:
        items = resource_catalog.scan_all(data_dir) if data_dir else []
        cache = self.cache_dir()
        if cache is not None:
            items.extend(resource_catalog.scan_cache(cache))
        return items

    @staticmethod
    def cache_dir() -> Path | None:
        """Папка скачанных изображений профиля (кэш игры)."""
        home = Path.home()
        for folder in ("Documents", "Документы"):
            path = home / folder / "TanksBlitz" / "image_cache"
            if path.is_dir():
                return path
        return None

    @staticmethod
    def directory_writable(directory) -> bool:
        """Можно ли писать в папку (проверка пробным файлом)."""
        if not directory:
            return False
        probe = Path(directory) / ".blc_write_test"
        try:
            probe.write_bytes(b"")
            probe.unlink()
            return True
        except OSError:
            return False

    def _on_images_scanned(self, items) -> None:
        self.busy_images = False
        if not self.directory_writable(self.cache_dir()):
            self.cache_writable = False
            LOG.warning("Папка кэша игры недоступна для записи: %s", self.cache_dir())
            self.toast.emit("Папка кэша игры защищена от записи — фоны профиля "
                            "не применятся. Разрешите BlitzCustom.exe в «Защите "
                            "от программ-шантажистов».", "error")
        else:
            self.cache_writable = True
        self.images = {item["id"]: item for item in items}
        self.settings.set("image_index", resource_catalog.index_payload(items))
        self.settings.set("image_index_version", INDEX_VERSION)
        self.settings.save()
        LOG.info("Индекс изображений: %d ресурсов", len(items))
        self.images_scanned.emit()

    def _on_images_failed(self, message: str) -> None:
        self.busy_images = False
        LOG.error("Индекс изображений не построен: %s", message)
        self.images_scanned.emit()

    def images_in(self, category: str) -> list[dict]:
        return [item for item in self.images.values() if item.get("category") == category]

    def resource_for(self, code: str):
        """Ресурс карты или изображения по идентификатору."""
        resource = self.scan.maps.get(code)
        if resource is not None and resource.found:
            return resource
        entry = self.images.get(code)
        return resource_catalog.to_map_resource(entry) if entry else None

    # -------------------------------------------------------- назначения
    def assignment(self, code: str) -> dict:
        return self.settings.assignments.get(code, {})

    def assigned_image(self, code: str) -> Path | None:
        raw = self.assignment(code).get("image")
        if not raw:
            return None
        path = Path(raw)
        return path if path.is_file() else None

    def assign(self, code: str, source: str | Path) -> dict:
        """Проверяет и копирует пользовательское изображение, сохраняет назначение."""
        info = validate_image(source)
        stored = copy_user_image(source, self.settings.custom_images_dir(), code)
        entry = self.settings.assignments.setdefault(code, {})
        entry.update({
            "image": str(stored),
            "applied": False,
            "assigned_at": time.time(),
            "source_size": [info.width, info.height],
        })
        self.settings.save()
        self.assignments_changed.emit()
        LOG.info("Назначено изображение для %s: %s", code, stored.name)
        return entry

    def reset_assignment(self, code: str) -> None:
        self.settings.assignments.pop(code, None)
        self.settings.save()
        self.assignments_changed.emit()

    def pending_codes(self) -> list[str]:
        return [code for code, item in self.settings.assignments.items()
                if item.get("image") and not item.get("applied")]

    def assigned_codes(self) -> list[str]:
        return [code for code, item in self.settings.assignments.items() if item.get("image")]

    # ---------------------------------------------------------- применение
    def apply(self, codes: list[str]) -> None:
        """Применяет назначенные изображения в фоне."""
        if self.busy_apply:
            return
        prepared = [code for code in codes if self.assignment(code).get("image")]
        if not prepared:
            self.toast.emit("Нет назначенных изображений для применения.", "info")
            return

        self.busy_apply = True
        self.apply_progress.emit(0, len(prepared))
        QTimer.singleShot(120_000, self._apply_watchdog)
        worker = _Worker(self._apply_task, prepared,
                         lambda done, total: self.apply_progress.emit(done, total))
        worker.signals.done.connect(self._on_applied)
        worker.signals.failed.connect(self._on_apply_failed)
        self.pool.start(worker)

    def _apply_task(self, codes: list[str], progress=None) -> dict:
        if is_game_running():
            raise RuntimeError("Tanks Blitz запущена. Закройте игру и повторите.")
        applied, skipped, errors = 0, 0, 0
        details: list[dict] = []
        for index, code in enumerate(codes):
            if progress is not None:
                progress(index, len(codes))
            entry = self._map_by_code.get(code) or {"code": code, "name": self.map_name(code)}
            resource = self.resource_for(code)
            image_path = self.assigned_image(code)
            if resource is None or not resource.found or image_path is None:
                skipped += 1
                details.append({"code": code, "status": "skipped",
                                "reason": "ресурс не найден" if image_path else "нет изображения"})
                continue
            try:
                result = apply_map(
                    entry, image_path, resource, self.backups,
                    quality=int(self.settings.get("quality", 90)),
                    crop_mode=str(self.settings.get("crop_mode", "cover")),
                    use_backup=bool(self.settings.get("backup_enabled", True)),
                )
                applied += 1
                details.append({"code": code, "status": "applied", "result": result})
                item = self.settings.assignments.setdefault(code, {})
                item.update({"applied": True, "applied_at": result["applied_at"]})
            except (ApplyError, BackupError) as exc:
                errors += 1
                details.append({"code": code, "status": "error", "reason": str(exc)})
                LOG.error("Ошибка применения %s: %s", code, exc)
            except Exception as exc:  # noqa: BLE001
                errors += 1
                details.append({"code": code, "status": "error", "reason": str(exc)})
                LOG.exception("Непредвиденная ошибка применения %s", code)
        return {"applied": applied, "skipped": skipped, "errors": errors, "details": details}

    def _apply_watchdog(self) -> None:
        """Страховка: применение не должно «висеть» вечно."""
        if not self.busy_apply:
            return
        self.busy_apply = False
        LOG.error("Применение не завершилось за 2 минуты — сброшено")
        self.toast.emit("Применение не отвечает. Проверьте журнал.", "error")
        self.apply_finished.emit({"applied": 0, "skipped": 0, "errors": 1,
                                  "details": []})

    def _on_applied(self, summary: dict) -> None:
        self.busy_apply = False
        self.last_apply = summary
        self.settings.save()
        self._add_history("apply", summary)
        self.apply_finished.emit(summary)
        self.assignments_changed.emit()

    def _on_apply_failed(self, message: str) -> None:
        self.busy_apply = False
        self.toast.emit(message, "error")
        self.apply_finished.emit({"applied": 0, "skipped": 0, "errors": 1, "details": []})

    # ------------------------------------------------------- восстановление
    def restore(self, codes: list[str]) -> None:
        if self.busy_apply:
            return
        if is_game_running():
            self.toast.emit("Tanks Blitz запущена. Закройте игру и повторите.", "error")
            return
        self.busy_apply = True
        worker = _Worker(self._restore_task, codes)
        worker.signals.done.connect(self._on_restored)
        worker.signals.failed.connect(self._on_restore_failed)
        self.pool.start(worker)

    def _restore_task(self, codes: list[str]) -> dict:
        restored, errors = 0, []
        for code in codes:
            try:
                result = restore_map(code, self.backups)
                restored += len(result["restored"])
                item = self.settings.assignments.setdefault(code, {})
                item["applied"] = False
                item.pop("applied_at", None)
            except (ApplyError, BackupError, OSError) as exc:
                errors.append(f"{code}: {exc}")
        return {"restored": restored, "errors": errors}

    def _on_restored(self, summary: dict) -> None:
        self.busy_apply = False
        self.settings.save()
        self._add_history("restore", summary)
        self.restore_finished.emit(summary)
        self.assignments_changed.emit()

    def _on_restore_failed(self, message: str) -> None:
        self.busy_apply = False
        self.toast.emit(message, "error")
        self.restore_finished.emit({"restored": 0, "errors": [message]})

    def restore_everything(self) -> None:
        if self.busy_apply:
            return
        codes = [item["code"] for item in self.backups.all_items()]
        if not codes:
            self.toast.emit("Резервных копий нет.", "info")
            return
        self.restore(codes)

    # ------------------------------------------------------------ разное
    def _add_history(self, kind: str, summary: dict) -> None:
        record = {"kind": kind, "at": time.time(),
                  "applied": summary.get("applied", 0),
                  "restored": summary.get("restored", 0),
                  "errors": len(summary.get("errors") or []) or summary.get("errors", 0)}
        self.history.insert(0, record)
        del self.history[40:]
        self.settings.set("history", self.history)
        self.settings.save()

    def backup_items(self) -> list[dict]:
        return self.backups.all_items()

    def stats(self) -> Stats:
        assigned = len(self.assigned_codes())
        pending = len(self.pending_codes())
        errors = sum(1 for record in self.history[:5] if record.get("errors"))
        return Stats(
            game_found=bool(self.game and self.game.found),
            game_path=str(self.game.root) if self.game and self.game.root else self.settings.get("game_root", ""),
            resources_found=self.scan.found,
            resources_total=self.scan.total or len(self.maps),
            assigned=assigned,
            pending=pending,
            errors=errors,
            backups=len(self.backups.all_items()),
            last_operations=self.history[:5],
        )

    def map_name(self, code: str) -> str:
        entry = self._map_by_code.get(code)
        if entry:
            return entry["name"]
        image = self.images.get(code)
        return image["name"] if image else code
