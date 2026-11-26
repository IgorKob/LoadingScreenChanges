"""Безопасная замена игровых ресурсов с проверкой и откатом."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from PIL import Image
import io

from backup_manager import BackupError, BackupManager
from dvpl import DvplError, build_dvpl, parse_dvpl
from image_processor import ImageError, game_image_size, prepare_image_bytes
from resource_scanner import MapResource
from utils import LOG, atomic_write_bytes

GAME_PROCESS = "tanksblitz.exe"
CREATE_NO_WINDOW = 0x08000000


class ApplyError(Exception):
    pass


def is_game_running() -> bool:
    """Проверяет процесс tanksblitz.exe без внешних зависимостей."""
    try:
        completed = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {GAME_PROCESS}", "/NH"],
            capture_output=True, text=True, timeout=15,
            creationflags=CREATE_NO_WINDOW,
        )
        return GAME_PROCESS in (completed.stdout or "").lower()
    except (OSError, subprocess.SubprocessError) as exc:
        LOG.warning("Не удалось проверить процессы игры: %s", exc)
        return False


def _verify_written(path: Path, expected_size: tuple[int, int]) -> None:
    data = path.read_bytes()
    payload, _ = parse_dvpl(data)
    with Image.open(io.BytesIO(payload)) as img:
        if img.size != expected_size:
            raise ApplyError(f"После записи размер изображения {img.size} не совпадает с {expected_size}.")


def apply_map(map_entry: dict,
              image_path: str | Path,
              resource: MapResource,
              backups: BackupManager,
              quality: int = 90,
              crop_mode: str = "cover",
              use_backup: bool = True) -> dict:
    """Заменяет загрузочные экраны карты (включая модификации) на изображение пользователя.

    При любой ошибке восстанавливает все уже изменённые файлы.
    """
    if not resource or not resource.found or not resource.files:
        raise ApplyError("Загрузочный экран этой карты не найден в ресурсах игры.")
    if is_game_running():
        raise ApplyError("Tanks Blitz запущена. Закройте игру и повторите применение — "
                         "иначе изменения не подхватятся или файлы будут заблокированы.")
    if not Path(image_path).is_file():
        raise ApplyError("Пользовательское изображение не найдено. Выберите его заново.")

    files = resource.files
    sizes: dict[tuple[int, int], bytes] = {}
    for record in files:
        target_path = Path(record["path"])
        if not target_path.is_file():
            raise ApplyError(f"Игровой файл исчез: {target_path}")
        try:
            size = game_image_size(target_path)
        except ImageError as exc:
            raise ApplyError(str(exc)) from exc
        if size not in sizes:
            try:
                sizes[size], _ = prepare_image_bytes(image_path, size, crop_mode, quality)
            except ImageError as exc:
                raise ApplyError(str(exc)) from exc

    written: list[tuple[Path, bytes | None, dict | None]] = []
    result_files: list[str] = []
    try:
        for record in files:
            target_path = Path(record["path"])
            size = game_image_size(target_path)
            payload = sizes[size]
            dvpl_bytes = build_dvpl(payload)
            # Проверяем, что контейнер корректен ещё до записи
            parse_dvpl(dvpl_bytes)

            backup_record = None
            original_bytes = None
            if use_backup:
                try:
                    backup_record = backups.ensure_backup(map_entry["code"], map_entry["name"], target_path)
                except BackupError as exc:
                    raise ApplyError(str(exc)) from exc
            else:
                original_bytes = target_path.read_bytes()

            # Проверка прав на запись в папку игры
            probe = target_path.with_name(target_path.name + ".blc_perm")
            try:
                probe.write_bytes(b"")
                probe.unlink()
            except OSError as exc:
                raise ApplyError(f"Недостаточно прав для изменения файлов игры: {exc}") from exc

            atomic_write_bytes(target_path, dvpl_bytes)
            written.append((target_path, original_bytes, backup_record))
            _verify_written(target_path, size)
            result_files.append(str(target_path))
            LOG.info("Заменён ресурс: %s", target_path)

        return {
            "code": map_entry["code"],
            "map": map_entry["name"],
            "files": result_files,
            "target_size": next(iter(sizes)),
            "applied_at": time.time(),
            "backup": use_backup,
        }
    except Exception as exc:
        LOG.error("Ошибка применения для %s: %s. Откатываем изменения.", map_entry.get("name"), exc)
        rollback_errors = []
        for target_path, original_bytes, backup_record in reversed(written):
            try:
                if backup_record is not None:
                    backups.restore_file(map_entry["code"], target_path)
                elif original_bytes is not None:
                    atomic_write_bytes(target_path, original_bytes)
            except Exception as rb_exc:  # noqa: BLE001
                rollback_errors.append(f"{target_path}: {rb_exc}")
        if rollback_errors:
            raise ApplyError(f"{exc}\n\nНе удалось полностью откатить изменения:\n" + "\n".join(rollback_errors)) from exc
        if isinstance(exc, ApplyError):
            raise
        raise ApplyError(f"Не удалось применить изменения: {exc}") from exc


def restore_map(code: str, backups: BackupManager) -> dict:
    item = backups.get(code)
    if not item:
        raise ApplyError("Для этой карты нет резервной копии.")
    errors = []
    restored = []
    for original_path in list((item.get("files") or {}).keys()):
        try:
            backups.restore_file(code, Path(original_path))
            restored.append(original_path)
        except (BackupError, OSError) as exc:
            errors.append(f"{original_path}: {exc}")
    if errors:
        raise ApplyError("Не удалось восстановить часть файлов:\n" + "\n".join(errors))
    LOG.info("Карта %s восстановлена из резервной копии", code)
    return {"code": code, "restored": restored}


def restore_all(backups: BackupManager) -> dict:
    items = [item["code"] for item in backups.all_items()]
    errors = []
    restored = 0
    for code in items:
        try:
            result = restore_map(code, backups)
            restored += len(result["restored"])
        except ApplyError as exc:
            errors.append(f"{code}: {exc}")
    return {"restored": restored, "errors": errors, "maps": len(items)}
