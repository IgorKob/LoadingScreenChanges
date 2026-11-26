"""Хранение пользовательских настроек в settings.json."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from utils import LOG, atomic_write_text, subdir, user_data_dir

DEFAULTS: dict = {
    "version": 1,
    "game_root": "",
    "data_dir": "",
    "loading_root": "",
    "game_version": "",
    "detected_source": "",
    "quality": 90,
    "crop_mode": "cover",          # cover | contain | stretch
    "backup_enabled": True,
    "confirm_apply": True,
    "assignments": {},             # code -> {image, applied, applied_at, files}
    "scan": {},                    # результаты последнего сканирования
    "window_geometry": "",
}


def _merge(defaults: dict, loaded: dict) -> dict:
    result = copy.deepcopy(defaults)
    for key, value in (loaded or {}).items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


class SettingsManager:
    def __init__(self, path: Path | None = None):
        self.path = path or (user_data_dir() / "settings.json")
        self.data = self.load()

    def load(self) -> dict:
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError("settings.json должен содержать объект")
            return _merge(DEFAULTS, loaded)
        except FileNotFoundError:
            data = copy.deepcopy(DEFAULTS)
            self.data = data
            self.save()
            return data
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            LOG.warning("Не удалось прочитать settings.json: %s", exc)
            return copy.deepcopy(DEFAULTS)

    def save(self) -> None:
        atomic_write_text(self.path, json.dumps(self.data, ensure_ascii=False, indent=2))

    # ---- удобные обёртки ----
    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value) -> None:
        self.data[key] = value

    @property
    def assignments(self) -> dict:
        return self.data.setdefault("assignments", {})

    def assignment(self, code: str) -> dict:
        return self.assignments.setdefault(code, {})

    def clear_assignment(self, code: str) -> None:
        self.assignments.pop(code, None)
        self.save()

    def custom_images_dir(self) -> Path:
        return subdir("custom_images")

    def backups_dir(self) -> Path:
        return subdir("backups")

    def logs_dir(self) -> Path:
        return subdir("logs")
