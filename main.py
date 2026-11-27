"""BlitzCustom — точка входа."""
from __future__ import annotations

import sys

from utils import APP_NAME, LOG, setup_logging


def _say(text: str) -> None:
    """Печать в консоль, если она есть: в windowed-сборке sys.stdout = None."""
    LOG.info(text)
    try:
        print(text)
    except Exception:  # noqa: BLE001 - консоли может не быть вовсе
        pass


def diagnose() -> int:
    """Диагностика без запуска интерфейса: python main.py --diagnose"""
    from game_detector import detect_game
    from map_database import load_catalog
    from resource_scanner import scan_resources
    from settings_manager import SettingsManager
    from utils import user_data_dir

    settings = SettingsManager()
    maps = load_catalog(user_data_dir() / "maps.json")
    info = detect_game(settings.get("game_root"), deep_search=True)
    _say(f"Игра найдена: {info.found}")
    _say(f"  Папка:    {info.root}")
    _say(f"  Ресурсы:  {info.loading_root}")
    _say(f"  Версия:   {info.version or '—'}")
    _say(f"  Источник: {info.source or '—'}")
    if info.error:
        _say(f"  Ошибка:   {info.error}")
    if info.loading_root:
        result = scan_resources(info.loading_root, maps)
        _say(f"Найдено карт: {result.found}/{result.total}")
        for item in maps:
            res = result.maps.get(item["code"])
            mark = "OK " if res and res.found else "-- "
            files = len(res.files) if res else 0
            _say(f"  {mark}{item['name']:<20} {item['code']:<14} файлов: {files}")
    return 0 if info.found else 1


def main() -> int:
    setup_logging()
    if "--diagnose" in sys.argv:
        return diagnose()
    try:
        from ui.app import run as run_ui
        run_ui()
    except Exception as exc:  # noqa: BLE001
        LOG.exception("Критическая ошибка")
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(APP_NAME, f"Критическая ошибка:\n{exc}\n\nПодробности в папке logs.")
            root.destroy()
        except Exception:  # noqa: BLE001
            _say(f"Критическая ошибка: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
