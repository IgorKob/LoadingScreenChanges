"""Автоматическое обнаружение Lesta Game Launcher и установленной Tanks Blitz."""
from __future__ import annotations

import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from utils import LOG

EXE_NAME = "tanksblitz.exe"
WOTB_APP_ID = "wotb.ru.production"


@dataclass
class GameInfo:
    root: Path | None = None
    exe: Path | None = None
    data_dir: Path | None = None
    loading_root: Path | None = None
    version: str = ""
    launcher: str = ""
    source: str = ""
    error: str = ""
    tried: list[str] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return self.root is not None and self.data_dir is not None

    @property
    def resources_ok(self) -> bool:
        return self.loading_root is not None


def _program_data() -> Path:
    return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))


def _appdata() -> Path:
    return Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))


def _localappdata() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))


def _read_version(root: Path) -> str:
    info = root / "game_info.xml"
    try:
        text = info.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"<version_name>\s*([^<]+?)\s*</version_name>", text)
        if m:
            return m.group(1)
    except OSError:
        pass
    version_file = root / "Data" / "version.txt.dvpl"
    try:
        from dvpl import read_dvpl
        payload, _ = read_dvpl(version_file)
        return payload.decode("utf-8", "ignore").strip()
    except Exception:
        return ""


def validate_game_root(root: str | Path) -> GameInfo | None:
    """Проверяет, что папка действительно содержит установленную Tanks Blitz."""
    try:
        root = Path(root).expanduser().resolve()
    except (OSError, ValueError):
        return None
    if not root.is_dir():
        return None

    exe = None
    try:
        for entry in root.iterdir():
            if entry.is_file() and entry.name.lower() == EXE_NAME:
                exe = entry
                break
    except OSError:
        return None
    if exe is None:
        return None

    data_dir = root / "Data"
    if not data_dir.is_dir():
        data_dir = root  # некоторые сборки хранят ресурсы в корне

    loading_root = data_dir / "Gfx" / "UI" / "BattleLoadingScreen"
    if not loading_root.is_dir():
        alt = root / "Gfx" / "UI" / "BattleLoadingScreen"
        loading_root = alt if alt.is_dir() else None

    info = GameInfo(
        root=root,
        exe=exe,
        data_dir=data_dir,
        loading_root=loading_root,
        version=_read_version(root),
    )
    LOG.info("Игра найдена: %s (версия %s), ресурсы: %s", root, info.version or "?", loading_root)
    return info


def _gamecenter_dirs() -> list[Path]:
    dirs = [
        _program_data() / "Lesta" / "GameCenter",
        _appdata() / "Lesta" / "GameCenter",
        _localappdata() / "Lesta" / "GameCenter",
    ]
    seen = set()
    result = []
    for d in dirs:
        if d.is_dir() and str(d).lower() not in seen:
            seen.add(str(d).lower())
            result.append(d)
    return result


def _candidates_from_apps(gc: Path) -> list[tuple[str, str]]:
    """Файлы в GameCenter/apps/<id>/ содержат путь установки игры."""
    result: list[tuple[str, str]] = []
    apps = gc / "apps"
    if not apps.is_dir():
        return result
    try:
        app_dirs = [p for p in apps.iterdir() if p.is_dir()]
    except OSError:
        return result
    for app in app_dirs:
        if WOTB_APP_ID not in app.name.lower():
            continue
        try:
            for entry in app.iterdir():
                if not entry.is_file():
                    continue
                try:
                    text = entry.read_text(encoding="utf-8", errors="ignore").strip()
                except OSError:
                    continue
                for line in text.splitlines():
                    line = line.strip().strip('"')
                    if line and re.match(r"^[A-Za-z]:\\", line):
                        result.append((line, f"Lesta Game Center ({entry.name[:8]}…)"))
        except OSError:
            continue
    return result


def _candidates_from_preferences(gc: Path) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for name in ("preferences.xml", "preferences.xml.bak"):
        path = gc / name
        if not path.is_file():
            continue
        try:
            tree = ET.parse(path)
        except (ET.ParseError, OSError):
            continue
        for node in tree.iter():
            if node.tag == "working_dir" and node.text:
                result.append((node.text.strip(), "Lesta Game Center (preferences.xml)"))
    return result


def _candidates_from_registry() -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    try:
        import winreg
    except ImportError:
        return result
    keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, base in keys:
        try:
            with winreg.OpenKey(hive, base) as root_key:
                for i in range(winreg.QueryInfoKey(root_key)[0]):
                    try:
                        sub_name = winreg.EnumKey(root_key, i)
                        with winreg.OpenKey(root_key, sub_name) as sub:
                            display = ""
                            location = ""
                            for value_name in ("DisplayName", "InstallLocation"):
                                try:
                                    val = winreg.QueryValueEx(sub, value_name)[0]
                                except OSError:
                                    continue
                                if value_name == "DisplayName":
                                    display = str(val)
                                else:
                                    location = str(val)
                            low = display.lower()
                            if ("tanks blitz" in low or "tanksblitz" in low or "wotb" in low) and location:
                                result.append((location, "Реестр Windows"))
                    except OSError:
                        continue
        except OSError:
            continue
    return result


def _common_candidates() -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    try:
        drives = [f"{chr(letter)}:\\" for letter in range(ord("C"), ord("Z") + 1)
                  if Path(f"{chr(letter)}:\\").exists()]
    except OSError:
        drives = ["C:\\"]
    names = [
        r"Games\Tanks_Blitz",
        r"Games\Tanks Blitz",
        r"Games\TanksBlitz",
        r"Tanks_Blitz",
        r"Tanks Blitz",
        r"Lesta\Tanks_Blitz",
        r"Lesta\Tanks Blitz",
        r"Program Files\Lesta\Tanks Blitz",
        r"Program Files (x86)\Lesta\Tanks Blitz",
        r"Program Files\Tanks Blitz",
        r"Program Files (x86)\Tanks Blitz",
    ]
    for drive in drives:
        for name in names:
            result.append((str(Path(drive) / name), "Стандартные папки"))
    return result


def _shallow_search(deadline: float) -> list[tuple[str, str]]:
    """Неглубокий поиск tanksblitz.exe в типичных местах (до 3 уровней)."""
    result: list[tuple[str, str]] = []
    roots: list[Path] = []
    for base in (_program_data() / "Lesta", _appdata() / "Lesta"):
        if base.is_dir():
            roots.append(base)
    try:
        drives = [Path(f"{chr(letter)}:\\") for letter in range(ord("C"), ord("Z") + 1)
                  if Path(f"{chr(letter)}:\\").exists()]
    except OSError:
        drives = [Path("C:\\")]
    for drive in drives:
        for name in ("Games", "Lesta", "Program Files", "Program Files (x86)"):
            candidate = drive / name
            if candidate.is_dir():
                roots.append(candidate)
    seen = set()
    for root in roots:
        if time.time() > deadline:
            break
        stack = [(root, 0)]
        while stack:
            if time.time() > deadline:
                break
            folder, depth = stack.pop()
            key = str(folder).lower()
            if key in seen:
                continue
            seen.add(key)
            try:
                with os.scandir(folder) as it:
                    for entry in it:
                        try:
                            if entry.is_file(follow_symlinks=False) and entry.name.lower() == EXE_NAME:
                                result.append((str(folder), "Быстрый поиск по дискам"))
                            elif entry.is_dir(follow_symlinks=False) and depth < 2:
                                stack.append((Path(entry.path), depth + 1))
                        except OSError:
                            continue
            except OSError:
                continue
    return result


def _unique(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen = set()
    out = []
    for path, source in pairs:
        key = os.path.normcase(os.path.normpath(path))
        if key in seen:
            continue
        seen.add(key)
        out.append((path, source))
    return out


def detect_game(saved_root: str | Path | None = None,
                deep_search: bool = True,
                deadline_seconds: float = 25.0) -> GameInfo:
    """Ищет игру. Возвращает GameInfo; при неудаче заполняет error и tried."""
    tried: list[str] = []
    deadline = time.time() + deadline_seconds

    if saved_root:
        tried.append(f"Сохранённый путь: {saved_root}")
        info = validate_game_root(saved_root)
        if info:
            info.source = "Сохранённый путь"
            return info

    candidates: list[tuple[str, str]] = []
    for gc in _gamecenter_dirs():
        candidates += _candidates_from_apps(gc)
        candidates += _candidates_from_preferences(gc)
    candidates += _candidates_from_registry()
    candidates += _common_candidates()

    for path, source in _unique(candidates):
        if time.time() > deadline:
            break
        tried.append(f"{source}: {path}")
        info = validate_game_root(path)
        if info:
            info.source = source
            info.launcher = _launcher_path()
            info.tried = tried
            return info

    if deep_search:
        for path, source in _unique(_shallow_search(deadline)):
            tried.append(f"{source}: {path}")
            info = validate_game_root(path)
            if info:
                info.source = source
                info.launcher = _launcher_path()
                info.tried = tried
                return info

    error = ("Tanks Blitz не найдена автоматически. Убедитесь, что игра установлена "
             "через Lesta Game Center, или укажите папку с tanksblitz.exe вручную.")
    LOG.warning("Игра не найдена. Проверено вариантов: %d", len(tried))
    return GameInfo(error=error, launcher=_launcher_path(), tried=tried)


def _launcher_path() -> str:
    for gc in _gamecenter_dirs():
        exe = gc / "lgc.exe"
        if exe.is_file():
            return str(exe)
    return ""
