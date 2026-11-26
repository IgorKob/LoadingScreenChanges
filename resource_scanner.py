"""Сканирование игровых ресурсов и сопоставление с каталогом карт."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from map_database import LOADING_FILENAMES
from utils import LOG


@dataclass
class MapResource:
    code: str
    name: str
    found: bool = False
    files: list[dict] = field(default_factory=list)   # {variant, path, size, mtime}
    primary: str = ""

    @property
    def variants_found(self) -> int:
        return len(self.files)


@dataclass
class ScanResult:
    timestamp: float = 0.0
    loading_root: str = ""
    found: int = 0
    total: int = 0
    maps: dict[str, MapResource] = field(default_factory=dict)
    unknown_dirs: list[str] = field(default_factory=list)
    error: str = ""

    def to_settings(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "loading_root": self.loading_root,
            "found": self.found,
            "total": self.total,
            "error": self.error,
            "unknown_dirs": self.unknown_dirs,
            "maps": {
                code: {
                    "found": res.found,
                    "primary": res.primary,
                    "files": res.files,
                }
                for code, res in self.maps.items()
            },
        }


def _find_loading_file(folder: Path) -> Path | None:
    for name in LOADING_FILENAMES:
        candidate = folder / name
        if candidate.is_file():
            return candidate
    # Регистронезависимый поиск
    try:
        for entry in folder.iterdir():
            if entry.is_file() and entry.name.lower() in {n.lower() for n in LOADING_FILENAMES}:
                return entry
    except OSError:
        pass
    return None


def scan_resources(loading_root: str | Path, maps: list[dict]) -> ScanResult:
    """Сканирует каталоги загрузочных экранов и сопоставляет их с картами."""
    result = ScanResult(timestamp=time.time(), total=len(maps))
    if not loading_root:
        result.error = "Папка игровых ресурсов не определена."
        return result

    root = Path(loading_root)
    result.loading_root = str(root)
    if not root.is_dir():
        result.error = f"Папка ресурсов не существует: {root}"
        return result

    known_dirs: set[str] = set()
    for item in maps:
        known_dirs.update(v.lower() for v in item["variants"])

    try:
        entries = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name.lower())
    except OSError as exc:
        result.error = f"Не удалось прочитать папку ресурсов: {exc}"
        return result

    # Предварительно находим файл в каждом каталоге
    dir_files: dict[str, Path] = {}
    for folder in entries:
        path = _find_loading_file(folder)
        if path is not None:
            dir_files[folder.name.lower()] = path
        if folder.name.lower() not in known_dirs:
            result.unknown_dirs.append(folder.name)

    for item in maps:
        res = MapResource(code=item["code"], name=item["name"])
        for variant in item["variants"]:
            path = dir_files.get(variant.lower())
            if path is None:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            res.files.append({
                "variant": variant,
                "path": str(path),
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            })
        if res.files:
            res.found = True
            res.primary = res.files[0]["path"]
            result.found += 1
        result.maps[item["code"]] = res

    LOG.info("Сканирование: найдено %d из %d карт, неизвестных каталогов: %d",
             result.found, result.total, len(result.unknown_dirs))
    return result


def scan_from_settings(settings_scan: dict) -> ScanResult:
    """Восстанавливает ScanResult из сохранённых настроек."""
    result = ScanResult(
        timestamp=float(settings_scan.get("timestamp") or 0),
        loading_root=settings_scan.get("loading_root", ""),
        found=int(settings_scan.get("found") or 0),
        total=int(settings_scan.get("total") or 0),
        error=settings_scan.get("error", ""),
        unknown_dirs=list(settings_scan.get("unknown_dirs") or []),
    )
    for code, data in (settings_scan.get("maps") or {}).items():
        files = list(data.get("files") or [])
        result.maps[code] = MapResource(
            code=code,
            name=code,
            found=bool(data.get("found")),
            files=files,
            primary=data.get("primary", ""),
        )
    return result
