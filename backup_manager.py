"""Резервное копирование и восстановление оригинальных ресурсов."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from utils import (LOG, atomic_write_bytes, atomic_write_text, human_size,
                   safe_filename, sha256_file)

MANIFEST_NAME = "manifest.json"


class BackupError(Exception):
    pass


class BackupManager:
    def __init__(self, backup_dir: Path):
        self.dir = backup_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.dir / MANIFEST_NAME
        self.manifest = self._load()

    def _load(self) -> dict:
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("items"), dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
        return {"version": 1, "items": {}}

    def _save(self) -> None:
        atomic_write_text(self.manifest_path, json.dumps(self.manifest, ensure_ascii=False, indent=2))

    def has_backup(self, code: str) -> bool:
        item = self.manifest["items"].get(code)
        if not item:
            return False
        return any((self.dir / f["backup_file"]).is_file() for f in item.get("files", {}).values())

    def get(self, code: str) -> dict | None:
        return self.manifest["items"].get(code)

    def all_items(self) -> list[dict]:
        result = []
        for code, item in self.manifest["items"].items():
            files = item.get("files", {})
            total = sum(f.get("size", 0) for f in files.values())
            result.append({
                "code": code,
                "map": item.get("map", code),
                "created_at": item.get("created_at", 0),
                "files": len(files),
                "size": total,
            })
        result.sort(key=lambda x: x["created_at"], reverse=True)
        return result

    def ensure_backup(self, code: str, map_name: str, original_path: Path) -> dict:
        """Создаёт резервную копию один раз; повторные замены её не перезаписывают."""
        if not original_path.is_file():
            raise BackupError(f"Оригинальный файл не найден: {original_path}")

        item = self.manifest["items"].setdefault(code, {
            "map": map_name,
            "created_at": time.time(),
            "files": {},
        })
        key = str(original_path)
        existing = item["files"].get(key)
        if existing:
            backup_path = self.dir / existing["backup_file"]
            if backup_path.is_file():
                return existing
            LOG.warning("Файл резервной копии потерян, создаём заново: %s", backup_path)

        stamp = time.strftime("%Y%m%d_%H%M%S")
        safe_map = original_path.parent.name
        backup_name = f"{safe_filename(code)}__{safe_map}__{stamp}.dvpl.bak"
        backup_path = self.dir / backup_name
        counter = 1
        while backup_path.exists():
            backup_path = self.dir / f"{safe_filename(code)}__{safe_map}__{stamp}_{counter}.dvpl.bak"
            counter += 1

        try:
            shutil.copy2(original_path, backup_path)
            digest = sha256_file(backup_path)
        except OSError as exc:
            raise BackupError(f"Не удалось создать резервную копию: {exc}") from exc

        record = {
            "backup_file": backup_path.name,
            "size": backup_path.stat().st_size,
            "sha256": digest,
            "created_at": time.time(),
        }
        item["files"][key] = record
        item["created_at"] = item.get("created_at") or time.time()
        self._save()
        LOG.info("Резервная копия: %s (%s)", backup_path.name, human_size(record["size"]))
        return record

    def restore_file(self, code: str, original_path: Path) -> None:
        item = self.manifest["items"].get(code)
        if not item:
            raise BackupError("Для этой карты нет резервной копии.")
        record = item["files"].get(str(original_path))
        if not record:
            raise BackupError("В резервной копии нет записи об этом файле.")
        backup_path = self.dir / record["backup_file"]
        if not backup_path.is_file():
            raise BackupError(f"Файл резервной копии не найден: {backup_path}")
        if sha256_file(backup_path) != record["sha256"]:
            raise BackupError("Резервная копия повреждена (не совпадает контрольная сумма).")

        data = backup_path.read_bytes()
        atomic_write_bytes(Path(original_path), data)
        LOG.info("Восстановлен оригинал: %s", original_path)

    def forget(self, code: str) -> None:
        """Удаляет записи манифеста (сами .bak остаются на диске)."""
        self.manifest["items"].pop(code, None)
        self._save()

    def file_records(self, code: str) -> list[dict]:
        item = self.manifest["items"].get(code) or {}
        result = []
        for path, rec in (item.get("files") or {}).items():
            result.append({"path": path, **rec})
        return result
