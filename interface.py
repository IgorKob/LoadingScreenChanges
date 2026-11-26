"""Графический интерфейс Blitz Loading Changer v0.3 (tkinter)."""
from __future__ import annotations

import os
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from backup_manager import BackupManager
from game_detector import GameInfo, detect_game, validate_game_root
from image_processor import (FORMATS_TEXT, ImageError, copy_user_image,
                             load_game_image, make_preview, validate_image)
from map_database import get_map
from resource_replacer import ApplyError, apply_map, restore_all, restore_map
from resource_scanner import MapResource, ScanResult, scan_resources
from settings_manager import SettingsManager
from utils import (APP_NAME, APP_VERSION, LOG, human_size, human_time,
                   user_data_dir)

BG = "#10151d"
PANEL = "#18212d"
PANEL_2 = "#202c3a"
BORDER = "#2b3a4c"
TEXT = "#eef3f8"
MUTED = "#9aabba"
ACCENT = "#f0a52b"
ACCENT_HOVER = "#ffbd4a"
GREEN = "#62c58b"
RED = "#e47777"
BLUE = "#6fa8dc"

PREVIEW_BOX = (380, 380)


class ScrollFrame(tk.Frame):
    """Прокручиваемый контейнер."""

    def __init__(self, parent, bg=PANEL, **kwargs):
        super().__init__(parent, bg=bg, **kwargs)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

    def _on_inner(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)

    def _bind_wheel(self, _event=None):
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self, _event=None):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")


class BlitzApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1280x840")
        self.root.minsize(1120, 720)
        self.root.configure(bg=BG)

        self.settings = SettingsManager()
        self.backups = BackupManager(self.settings.backups_dir())
        self.maps = self._load_catalog()
        self.game: GameInfo | None = None
        self.scan: ScanResult | None = None
        self.selected_code: str | None = self.maps[0]["code"] if self.maps else None
        self.search_var = tk.StringVar()
        self.busy = False
        self._bg_callback = None
        self._photos: list[ImageTk.PhotoImage] = []
        self.nav_buttons: dict[str, tk.Button] = {}
        self.pages: dict[str, tk.Frame] = {}

        self._build_styles()
        self._build_ui()
        self._restore_geometry()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(120, self.startup)

    # ------------------------------------------------------------------ данные
    def _load_catalog(self):
        from map_database import load_catalog
        return load_catalog(user_data_dir() / "maps.json")

    def _scan_map(self, code: str) -> MapResource | None:
        if self.scan:
            return self.scan.maps.get(code)
        return None

    def _assignment(self, code: str) -> dict:
        return self.settings.assignments.get(code, {})

    def _is_applied(self, code: str) -> bool:
        return bool(self._assignment(code).get("applied"))

    def _counts(self) -> tuple[int, int, int]:
        found = self.scan.found if self.scan else 0
        total = len(self.maps)
        configured = sum(1 for m in self.maps if self._assignment(m["code"]).get("image"))
        applied = sum(1 for m in self.maps if self._is_applied(m["code"]))
        return found, configured, applied

    # -------------------------------------------------------------------- стиль
    def _build_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Dark.Treeview",
                        background=PANEL_2, fieldbackground=PANEL_2, foreground=TEXT,
                        rowheight=30, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Dark.Treeview.Heading",
                        background=PANEL, foreground=MUTED, relief="flat",
                        font=("Segoe UI", 9, "bold"))
        style.map("Dark.Treeview", background=[("selected", ACCENT)],
                  foreground=[("selected", "#111820")])
        style.map("Dark.Treeview.Heading", background=[("active", PANEL_2)])
        style.configure("Dark.TCombobox",
                        fieldbackground="#0f151d", background=PANEL_2,
                        foreground=TEXT, arrowcolor=TEXT, borderwidth=0)
        style.map("Dark.TCombobox",
                  fieldbackground=[("readonly", "#0f151d")],
                  foreground=[("readonly", TEXT)])
        style.configure("Vertical.TScrollbar", background=PANEL_2, troughcolor=PANEL,
                        borderwidth=0, arrowcolor=MUTED)

    # ----------------------------------------------------------------------- UI
    def _make_button(self, parent, text, command, primary=False, danger=False, width=None):
        if primary:
            bg, fg, active = ACCENT, "#111820", ACCENT_HOVER
        elif danger:
            bg, fg, active = "#3a2226", RED, "#4a2b30"
        else:
            bg, fg, active = PANEL_2, TEXT, "#2b3b4d"
        return tk.Button(
            parent, text=text, command=command, bg=bg, fg=fg,
            activebackground=active, activeforeground=fg,
            relief="flat", bd=0, padx=14, pady=9,
            font=("Segoe UI", 10, "bold" if primary else "normal"),
            cursor="hand2", width=width,
        )

    def _card(self, parent):
        return tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)

    def _label(self, parent, text, size=10, color=TEXT, bold=False, bg=PANEL, **kwargs):
        return tk.Label(parent, text=text, bg=bg, fg=color,
                        font=("Segoe UI", size, "bold" if bold else "normal"), **kwargs)

    def _build_ui(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=24, pady=(16, 10))

        title_box = tk.Frame(header, bg=BG)
        title_box.pack(side="left")
        tk.Label(title_box, text="BLITZ", bg=BG, fg=ACCENT,
                 font=("Segoe UI Black", 24)).pack(side="left")
        tk.Label(title_box, text=" LOADING CHANGER", bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 18)).pack(side="left", pady=(5, 0))
        tk.Label(title_box, text=f" v{APP_VERSION}", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(side="left", pady=(12, 0))

        right = tk.Frame(header, bg=BG)
        right.pack(side="right")
        self.header_status = tk.Label(right, text="ПОИСК ИГРЫ…", bg=PANEL_2, fg=MUTED,
                                      font=("Segoe UI", 8, "bold"), padx=10, pady=6)
        self.header_status.pack(side="right")
        tk.Label(right, text="КЛАССИЧЕСКИЙ РЕЖИМ 7×7 · 33 КАРТЫ", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(side="right", padx=(0, 12))

        nav = tk.Frame(self.root, bg=BG)
        nav.pack(fill="x", padx=24, pady=(0, 10))
        for key, title in (("home", "Главная"), ("maps", "Карты"),
                           ("settings", "Настройки"), ("backups", "Резервные копии")):
            btn = tk.Button(nav, text=title, command=lambda k=key: self.show_page(k),
                            bg=BG, fg=MUTED, activebackground=BG, activeforeground=TEXT,
                            relief="flat", bd=0, padx=16, pady=8,
                            font=("Segoe UI", 10, "bold"), cursor="hand2")
            btn.pack(side="left", padx=(0, 4))
            self.nav_buttons[key] = btn

        self.body = tk.Frame(self.root, bg=BG)
        self.body.pack(fill="both", expand=True, padx=24, pady=(0, 8))

        self._build_home_page()
        self._build_maps_page()
        self._build_settings_page()
        self._build_backups_page()

        statusbar = tk.Frame(self.root, bg=BG)
        statusbar.pack(fill="x", padx=24, pady=(0, 10))
        self.status_label = tk.Label(statusbar, text="Готово", bg=BG, fg=MUTED,
                                     anchor="w", font=("Segoe UI", 9))
        self.status_label.pack(side="left")
        self.data_label = tk.Label(statusbar, text=f"Данные: {user_data_dir()}", bg=BG,
                                   fg=MUTED, anchor="e", font=("Segoe UI", 8))
        self.data_label.pack(side="right")

        self.show_page("home")

    # ------------------------------------------------------------------ Главная
    def _build_home_page(self):
        page = tk.Frame(self.body, bg=BG)
        self.pages["home"] = page

        game_card = self._card(page)
        game_card.pack(fill="x")
        top = tk.Frame(game_card, bg=PANEL)
        top.pack(fill="x", padx=18, pady=(16, 6))
        self._label(top, "ИГРА", 11, bold=True).pack(side="left")
        self.game_state = tk.Label(top, text="НЕ НАЙДЕНА", bg=PANEL_2, fg=MUTED,
                                   font=("Segoe UI", 8, "bold"), padx=10, pady=5)
        self.game_state.pack(side="right")

        self.game_path_label = self._label(game_card, "Путь к игре не определён", 10, color=MUTED, anchor="w")
        self.game_path_label.pack(fill="x", padx=18)
        self.game_data_label = self._label(game_card, "Игровые ресурсы: —", 9, color=MUTED, anchor="w")
        self.game_data_label.pack(fill="x", padx=18, pady=(4, 0))
        self.game_extra_label = self._label(game_card, "Версия: — · Источник: —", 9, color=MUTED, anchor="w")
        self.game_extra_label.pack(fill="x", padx=18, pady=(4, 12))

        actions = tk.Frame(game_card, bg=PANEL)
        actions.pack(fill="x", padx=18, pady=(0, 16))
        self._make_button(actions, "Определить игру", self.detect_async, primary=True).pack(side="left")
        self._make_button(actions, "Указать папку вручную", self.choose_game_folder).pack(side="left", padx=8)
        self._make_button(actions, "Сканировать ресурсы", self.scan_async).pack(side="left")
        self._make_button(actions, "Применить все изменения", self.apply_all, primary=True).pack(side="right")

        stats = tk.Frame(page, bg=BG)
        stats.pack(fill="x", pady=(14, 0))
        self.stat_found = self._stat_tile(stats, "НАЙДЕНО РЕСУРСОВ", "0 / 33")
        self.stat_configured = self._stat_tile(stats, "НАСТРОЕНО КАРТ", "0 / 33")
        self.stat_applied = self._stat_tile(stats, "ИЗМЕНЕНО В ИГРЕ", "0 / 33")
        for tile in (self.stat_found, self.stat_configured, self.stat_applied):
            tile.pack(side="left", fill="both", expand=True, padx=(0, 12))

        scan_card = self._card(page)
        scan_card.pack(fill="both", expand=True, pady=(14, 0))
        head = tk.Frame(scan_card, bg=PANEL)
        head.pack(fill="x", padx=18, pady=(16, 4))
        self._label(head, "ПОСЛЕДНЕЕ СКАНИРОВАНИЕ", 11, bold=True).pack(side="left")
        self.scan_time_label = self._label(head, "ещё не выполнялось", 9, color=MUTED)
        self.scan_time_label.pack(side="right")

        self.scan_summary = self._label(scan_card, "Нажмите «Сканировать ресурсы», чтобы найти загрузочные экраны.",
                                        10, color=MUTED, anchor="w", justify="left", wraplength=1180)
        self.scan_summary.pack(fill="x", padx=18, pady=(6, 10))

        self.scan_list = tk.Text(scan_card, height=7, bg="#0f151d", fg=TEXT, relief="flat",
                                 font=("Consolas", 9), wrap="word", padx=10, pady=8,
                                 insertbackground=TEXT, highlightthickness=0)
        self.scan_list.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        self.scan_list.configure(state="disabled")

        note = self._label(
            page,
            "Заменяются только загрузочные экраны карт классического режима 7×7. "
            "Перед каждой заменой создаётся резервная копия, изменения можно отменить на вкладке "
            "«Резервные копии». Обновление игры может вернуть оригинальные изображения — "
            "после обновления выполните повторное сканирование.",
            8, color=MUTED, bg=BG, anchor="w", justify="left", wraplength=1200)
        note.pack(fill="x", pady=(10, 0))

    def _stat_tile(self, parent, caption, value):
        frame = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        inner = tk.Frame(frame, bg=PANEL)
        inner.pack(fill="both", expand=True, padx=16, pady=14)
        tk.Label(inner, text=value, bg=PANEL, fg=TEXT,
                 font=("Segoe UI Semibold", 22), anchor="w").pack(fill="x")
        tk.Label(inner, text=caption, bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", pady=(2, 0))
        frame.value_label = inner.winfo_children()[0]
        return frame

    # -------------------------------------------------------------------- Карты
    def _build_maps_page(self):
        page = tk.Frame(self.body, bg=BG)
        self.pages["maps"] = page

        left = tk.Frame(page, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, width=310)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Label(left, text="КАРТЫ 7×7", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=16, pady=(16, 2))
        tk.Label(left, text="33 карты классического режима", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(0, 10))
        search = tk.Entry(left, textvariable=self.search_var, bg="#0f151d", fg=TEXT,
                          insertbackground=TEXT, relief="flat", font=("Segoe UI", 9))
        search.pack(fill="x", padx=12, ipady=7)
        search.insert(0, "")
        self.search_var.trace_add("write", lambda *_: self.refresh_map_list())

        self.map_scroll = ScrollFrame(left, bg=PANEL)
        self.map_scroll.pack(fill="both", expand=True, padx=8, pady=(8, 12))
        self.map_list = self.map_scroll.inner

        right = tk.Frame(page, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=(16, 0))

        card = self._card(right)
        card.pack(fill="both", expand=True)

        head = tk.Frame(card, bg=PANEL)
        head.pack(fill="x", padx=18, pady=(16, 8))
        self.map_title = tk.Label(head, text="Выберите карту", bg=PANEL, fg=TEXT,
                                  font=("Segoe UI Semibold", 18))
        self.map_title.pack(side="left")
        self.map_status = tk.Label(head, text="", bg=PANEL_2, fg=MUTED,
                                   font=("Segoe UI", 8, "bold"), padx=10, pady=5)
        self.map_status.pack(side="right")

        previews = tk.Frame(card, bg=PANEL)
        previews.pack(fill="both", expand=True, padx=18, pady=(0, 8))
        self.orig_caption, self.orig_preview = self._preview_slot(previews, "ОРИГИНАЛ ИЗ ИГРЫ")
        self.user_caption, self.user_preview = self._preview_slot(previews, "ВАШЕ ИЗОБРАЖЕНИЕ")

        info = tk.Frame(card, bg=PANEL)
        info.pack(fill="x", padx=18)
        self.orig_info = self._label(info, "Оригинал: —", 9, color=MUTED, anchor="w")
        self.orig_info.pack(fill="x")
        self.user_info = self._label(info, "Ваше изображение: не выбрано", 9, color=MUTED, anchor="w")
        self.user_info.pack(fill="x", pady=(2, 0))
        self.target_info = self._label(info, "Файл игры: —", 9, color=MUTED, anchor="w")
        self.target_info.pack(fill="x", pady=(2, 0))

        buttons = tk.Frame(card, bg=PANEL)
        buttons.pack(fill="x", padx=18, pady=(12, 18))
        self._make_button(buttons, "Выбрать изображение", self.choose_image, primary=True).pack(side="left")
        self._make_button(buttons, "Удалить изображение", self.remove_image).pack(side="left", padx=8)
        self._make_button(buttons, "Сбросить к оригиналу", self.reset_map, danger=True).pack(side="left")
        self._make_button(buttons, "Применить изменения", self.apply_selected, primary=True).pack(side="right")

    def _preview_slot(self, parent, caption):
        wrapper = tk.Frame(parent, bg=PANEL)
        wrapper.pack(side="left", fill="both", expand=True, padx=(0, 10))
        caption_label = tk.Label(wrapper, text=caption, bg=PANEL, fg=MUTED,
                                 font=("Segoe UI", 8, "bold"))
        caption_label.pack(anchor="w", pady=(0, 6))
        area = tk.Frame(wrapper, bg="#0b1017", highlightbackground=BORDER, highlightthickness=1)
        area.pack(fill="both", expand=True)
        preview_label = tk.Label(area, text="Нет изображения", bg="#0b1017", fg=MUTED,
                                 font=("Segoe UI", 10))
        preview_label.pack(fill="both", expand=True)
        return caption_label, preview_label

    # ---------------------------------------------------------------- Настройки
    def _build_settings_page(self):
        page = tk.Frame(self.body, bg=BG)
        self.pages["settings"] = page

        card = self._card(page)
        card.pack(fill="both", expand=True)
        self._label(card, "НАСТРОЙКИ", 12, bold=True).pack(anchor="w", padx=18, pady=(16, 10))

        form = tk.Frame(card, bg=PANEL)
        form.pack(fill="x", padx=18)

        self._label(form, "Папка игры", 10, bold=True).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.settings_game_var = tk.StringVar(value=self.settings.get("game_root", ""))
        entry = tk.Entry(form, textvariable=self.settings_game_var, bg="#0f151d", fg=TEXT,
                         insertbackground=TEXT, relief="flat", font=("Segoe UI", 9))
        entry.grid(row=1, column=0, sticky="ew", ipady=8)
        self._make_button(form, "Обзор…", self.choose_game_folder).grid(row=1, column=1, padx=(8, 0))
        self._make_button(form, "Определить автоматически", self.detect_async, primary=True).grid(row=1, column=2, padx=(8, 0))
        form.columnconfigure(0, weight=1)

        self.settings_data_label = self._label(form, "Папка ресурсов: —", 9, color=MUTED, anchor="w")
        self.settings_data_label.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))

        self._label(form, "Качество результирующего изображения (WebP)", 10, bold=True).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(18, 4))
        quality_row = tk.Frame(form, bg=PANEL)
        quality_row.grid(row=4, column=0, columnspan=3, sticky="w")
        self.quality_var = tk.IntVar(value=int(self.settings.get("quality", 90)))
        self.quality_scale = tk.Scale(
            quality_row, from_=60, to=100, orient="horizontal", variable=self.quality_var,
            bg=PANEL, fg=TEXT, highlightthickness=0, troughcolor="#0f151d",
            activebackground=ACCENT, length=320, font=("Segoe UI", 9), showvalue=0,
            command=lambda _v: self.quality_value.config(text=f"{self.quality_var.get()}%"))
        self.quality_scale.pack(side="left")
        self.quality_value = self._label(quality_row, f"{self.quality_var.get()}%", 10, color=ACCENT, bold=True)
        self.quality_value.pack(side="left", padx=10)

        self._label(form, "Кадрирование при несовпадении пропорций", 10, bold=True).grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(16, 4))
        self.crop_var = tk.StringVar(value=self.settings.get("crop_mode", "cover"))
        crop_row = tk.Frame(form, bg=PANEL)
        crop_row.grid(row=6, column=0, columnspan=3, sticky="w")
        for value, text in (("cover", "Заполнить с обрезкой"),
                            ("contain", "Вписать целиком"),
                            ("stretch", "Растянуть")):
            tk.Radiobutton(crop_row, text=text, value=value, variable=self.crop_var,
                           bg=PANEL, fg=TEXT, selectcolor="#0f151d", activebackground=PANEL,
                           activeforeground=TEXT, font=("Segoe UI", 9), bd=0,
                           highlightthickness=0).pack(side="left", padx=(0, 18))

        self.backup_var = tk.BooleanVar(value=bool(self.settings.get("backup_enabled", True)))
        tk.Checkbutton(form, text="Создавать резервные копии перед заменой (рекомендуется)",
                       variable=self.backup_var, bg=PANEL, fg=TEXT, selectcolor="#0f151d",
                       activebackground=PANEL, activeforeground=TEXT, bd=0,
                       highlightthickness=0, font=("Segoe UI", 9)).grid(
            row=7, column=0, columnspan=3, sticky="w", pady=(18, 2))
        self.confirm_var = tk.BooleanVar(value=bool(self.settings.get("confirm_apply", True)))
        tk.Checkbutton(form, text="Спрашивать подтверждение перед применением",
                       variable=self.confirm_var, bg=PANEL, fg=TEXT, selectcolor="#0f151d",
                       activebackground=PANEL, activeforeground=TEXT, bd=0,
                       highlightthickness=0, font=("Segoe UI", 9)).grid(
            row=8, column=0, columnspan=3, sticky="w", pady=(2, 12))

        buttons = tk.Frame(form, bg=PANEL)
        buttons.grid(row=9, column=0, columnspan=3, sticky="w", pady=(6, 18))
        self._make_button(buttons, "Сохранить настройки", self.save_settings, primary=True).pack(side="left")
        self._make_button(buttons, "Сканировать ресурсы", self.scan_async).pack(side="left", padx=8)
        self._make_button(buttons, "Открыть папку данных", self.open_data_folder).pack(side="left")
        self._make_button(buttons, "Открыть логи", self.open_logs_folder).pack(side="left", padx=8)

        self.settings_note = self._label(
            form,
            "Резервные копии, пользовательские изображения и журналы хранятся отдельно от игры. "
            "Файлы игры изменяются только по кнопке «Применить изменения».",
            8, color=MUTED, anchor="w", justify="left", wraplength=1100)
        self.settings_note.grid(row=10, column=0, columnspan=3, sticky="w", pady=(0, 16))

    # ------------------------------------------------------------ Резервные копии
    def _build_backups_page(self):
        page = tk.Frame(self.body, bg=BG)
        self.pages["backups"] = page

        card = self._card(page)
        card.pack(fill="both", expand=True)
        head = tk.Frame(card, bg=PANEL)
        head.pack(fill="x", padx=18, pady=(16, 10))
        self._label(head, "РЕЗЕРВНЫЕ КОПИИ", 12, bold=True).pack(side="left")
        self._make_button(head, "Обновить", self.refresh_backups).pack(side="right")

        columns = ("map", "files", "size", "date")
        self.backup_tree = ttk.Treeview(card, columns=columns, show="headings",
                                        style="Dark.Treeview", selectmode="browse")
        headings = {"map": "Карта", "files": "Файлов", "size": "Размер", "date": "Дата копии"}
        widths = {"map": 380, "files": 90, "size": 120, "date": 200}
        for col in columns:
            self.backup_tree.heading(col, text=headings[col])
            self.backup_tree.column(col, width=widths[col], anchor="w")
        self.backup_tree.pack(fill="both", expand=True, padx=18)

        buttons = tk.Frame(card, bg=PANEL)
        buttons.pack(fill="x", padx=18, pady=16)
        self._make_button(buttons, "Восстановить выбранную", self.restore_selected_backup, primary=True).pack(side="left")
        self._make_button(buttons, "Восстановить все", self.restore_all_backups, danger=True).pack(side="left", padx=8)
        self._label(buttons, "Оригиналы восстанавливаются из папки backups",
                    9, color=MUTED).pack(side="right")

    # ------------------------------------------------------------------ страницы
    def show_page(self, name: str):
        for key, page in self.pages.items():
            if key == name:
                page.pack(fill="both", expand=True)
            else:
                page.pack_forget()
        for key, btn in self.nav_buttons.items():
            active = key == name
            btn.configure(fg=ACCENT if active else MUTED,
                          font=("Segoe UI", 10, "bold"),
                          bg=PANEL_2 if active else BG)
        if name == "backups":
            self.refresh_backups()
        elif name == "maps":
            self.refresh_map_list()
            self.select_map(self.selected_code)

    # ------------------------------------------------------------------- статусы
    def set_status(self, text: str):
        self.status_label.config(text=text)

    def refresh_status(self):
        found, configured, applied = self._counts()
        total = len(self.maps)
        self.stat_found.value_label.config(text=f"{found} / {total}")
        self.stat_configured.value_label.config(text=f"{configured} / {total}")
        self.stat_applied.value_label.config(text=f"{applied} / {total}")

        if self.game and self.game.found:
            self.header_status.config(text="ИГРА НАЙДЕНА", fg=GREEN, bg="#16301f")
            self.game_state.config(text="НАЙДЕНА", fg=GREEN, bg="#16301f")
            self.game_path_label.config(text=str(self.game.root), fg=TEXT)
            self.game_data_label.config(text=f"Игровые ресурсы: {self.game.loading_root or 'не найдены'}")
            self.game_extra_label.config(
                text=f"Версия: {self.game.version or '—'} · Источник: {self.game.source or '—'}")
            self.settings_data_label.config(
                text=f"Папка ресурсов: {self.game.loading_root or '—'}")
        else:
            self.header_status.config(text="ИГРА НЕ НАЙДЕНА", fg=RED, bg="#3a2226")
            self.game_state.config(text="НЕ НАЙДЕНА", fg=RED, bg="#3a2226")
            self.game_path_label.config(
                text=self.game.error if self.game and self.game.error else "Путь к игре не определён",
                fg=MUTED)
            self.game_data_label.config(text="Игровые ресурсы: —")
            self.game_extra_label.config(text="Версия: — · Источник: —")
            self.settings_data_label.config(text="Папка ресурсов: —")

        self.refresh_scan_summary()
        self.refresh_map_list()
        self.refresh_selected_map()

    def refresh_scan_summary(self):
        if not self.scan:
            self.scan_time_label.config(text="ещё не выполнялось")
            self.scan_summary.config(text="Нажмите «Сканировать ресурсы», чтобы найти загрузочные экраны.")
            return
        self.scan_time_label.config(text=human_time(self.scan.timestamp))
        missing = [m["name"] for m in self.maps
                   if not (self.scan.maps.get(m["code"]) and self.scan.maps[m["code"]].found)]
        self.scan_summary.config(
            text=f"Найдено {self.scan.found} из {self.scan.total} карт. "
                 + (f"Не найдены: {', '.join(missing)}." if missing else "Все карты найдены."))
        lines = []
        for m in self.maps:
            res = self.scan.maps.get(m["code"])
            if res and res.found:
                lines.append(f"✓ {m['name']:<18} {res.files[0]['path']}")
            else:
                lines.append(f"✗ {m['name']:<18} загрузочный экран не найден")
        if self.scan.unknown_dirs:
            lines.append("")
            lines.append("Каталоги вне каталога карт (не изменяются): " + ", ".join(self.scan.unknown_dirs))
        self.scan_list.configure(state="normal")
        self.scan_list.delete("1.0", "end")
        self.scan_list.insert("1.0", "\n".join(lines))
        self.scan_list.configure(state="disabled")

    # ------------------------------------------------------------------ список карт
    def _map_state(self, code: str) -> tuple[str, str]:
        if self._is_applied(code):
            return "ИЗМЕНЕНО", GREEN
        if self._assignment(code).get("image"):
            return "НАСТРОЕНО", ACCENT
        res = self._scan_map(code)
        if res and res.found:
            return "НАЙДЕНО", MUTED
        return "НЕ НАЙДЕНО", RED

    def refresh_map_list(self):
        if not hasattr(self, "map_list"):
            return
        for child in self.map_list.winfo_children():
            child.destroy()
        query = self.search_var.get().strip().lower()
        for item in self.maps:
            if query and query not in item["name"].lower() and query not in item["code"].lower():
                continue
            code = item["code"]
            selected = code == self.selected_code
            state_text, state_color = self._map_state(code)
            row = tk.Frame(self.map_list, bg=ACCENT if selected else PANEL_2)
            row.pack(fill="x", pady=2)
            name = tk.Label(row, text=("▸ " if selected else "   ") + item["name"],
                            bg=ACCENT if selected else PANEL_2,
                            fg="#111820" if selected else TEXT,
                            anchor="w", padx=6, pady=9,
                            font=("Segoe UI", 10, "bold" if selected else "normal"))
            name.pack(side="left", fill="x", expand=True)
            dot = tk.Label(row, text="●", bg=ACCENT if selected else PANEL_2,
                           fg="#111820" if selected else state_color,
                           font=("Segoe UI", 9), padx=8)
            dot.pack(side="right")
            for widget in (row, name, dot):
                widget.configure(cursor="hand2")
                widget.bind("<Button-1>", lambda _e, c=code: self.select_map(c))

    def select_map(self, code: str | None):
        if not code:
            return
        item = get_map(self.maps, code)
        if not item:
            return
        self.selected_code = code
        self.refresh_map_list()
        self.refresh_selected_map()

    def refresh_selected_map(self):
        if not self.selected_code:
            return
        item = get_map(self.maps, self.selected_code)
        if not item:
            return
        code = item["code"]
        self.map_title.config(text=item["name"])
        state_text, state_color = self._map_state(code)
        self.map_status.config(text=state_text, fg=state_color,
                               bg="#16301f" if state_text == "ИЗМЕНЕНО" else PANEL_2)

        res = self._scan_map(code)
        if res and res.found:
            self.orig_info.config(text=f"Оригинал: {res.primary}")
            self.target_info.config(
                text=f"Файл игры: {Path(res.primary).name} · модификаций: {len(res.files)}")
        else:
            self.orig_info.config(text="Оригинал: загрузочный экран не найден в ресурсах игры")
            self.target_info.config(text="Файл игры: —")

        assignment = self._assignment(code)
        image_path = assignment.get("image", "")
        if image_path and Path(image_path).is_file():
            try:
                info = validate_image(image_path)
                applied = " · применено" if assignment.get("applied") else ""
                self.user_info.config(text=f"Ваше изображение: {info.text} · {info.format}{applied}\n{image_path}")
            except ImageError:
                self.user_info.config(text=f"Ваше изображение: {image_path} (файл недоступен)")
        else:
            self.user_info.config(text="Ваше изображение: не выбрано")

        self._show_previews(code, res, image_path)

    def _show_previews(self, code: str, res: MapResource | None, image_path: str):
        self._photos.clear()
        # Оригинал
        if res and res.found:
            try:
                with load_game_image(res.primary) as img:
                    size = img.size
                    preview = make_preview(img, PREVIEW_BOX)
                photo = ImageTk.PhotoImage(preview)
                self._photos.append(photo)
                self.orig_preview.config(image=photo, text="", bg="#0b1017")
                self.orig_info.config(text=f"Оригинал: {size[0]} × {size[1]} · {Path(res.primary).name}")
            except (ImageError, OSError) as exc:
                self.orig_preview.config(image="", text=f"Ошибка предпросмотра:\n{exc}")
        else:
            self.orig_preview.config(image="", text="Оригинал не найден")

        # Пользовательское
        if image_path and Path(image_path).is_file():
            try:
                with Image.open(image_path) as img:
                    img.load()
                    preview = make_preview(img, PREVIEW_BOX)
                photo = ImageTk.PhotoImage(preview)
                self._photos.append(photo)
                self.user_preview.config(image=photo, text="", bg="#0b1017")
            except Exception as exc:  # noqa: BLE001
                self.user_preview.config(image="", text=f"Ошибка предпросмотра:\n{exc}")
        else:
            self.user_preview.config(image="", text="Изображение не выбрано")

    # -------------------------------------------------------------- обнаружение
    def startup(self):
        saved = self.settings.get("game_root", "")
        info = validate_game_root(saved) if saved else None
        if info:
            info.source = "Сохранённый путь"
            self._set_game(info)
            self.scan_async()
        else:
            self.detect_async(silent=True)

    def detect_async(self, silent: bool = False):
        if self.busy:
            return
        saved = self.settings_game_var.get().strip() or self.settings.get("game_root", "")
        self._run_bg(
            "Поиск игры…",
            lambda: detect_game(saved, deep_search=True),
            lambda info: self._after_detect(info, silent),
        )

    def _after_detect(self, info: GameInfo, silent: bool):
        self.game = info
        if info.found:
            self._set_game(info)
            self.scan_async()
            if not silent:
                messagebox.showinfo(APP_NAME, f"Игра найдена.\n\n{info.root}\nВерсия: {info.version or '—'}")
        else:
            self.scan = None
            self.refresh_status()
            self.set_status("Игра не найдена")
            if not silent:
                messagebox.showerror(APP_NAME, info.error + "\n\nУкажите папку игры вручную в настройках.")

    def _set_game(self, info: GameInfo):
        self.game = info
        self.settings.set("game_root", str(info.root) if info.root else "")
        self.settings.set("data_dir", str(info.data_dir) if info.data_dir else "")
        self.settings.set("loading_root", str(info.loading_root) if info.loading_root else "")
        self.settings.set("game_version", info.version)
        self.settings.set("detected_source", info.source)
        self.settings_game_var.set(str(info.root) if info.root else "")
        self.settings.save()
        self.refresh_status()

    def choose_game_folder(self):
        folder = filedialog.askdirectory(title="Выберите папку с tanksblitz.exe")
        if not folder:
            return
        info = validate_game_root(folder)
        if not info:
            messagebox.showerror(APP_NAME, "В выбранной папке не найден tanksblitz.exe или папка Data.\n"
                                           "Укажите корневую папку установленной Tanks Blitz.")
            return
        info.source = "Указано вручную"
        self._set_game(info)
        self.scan_async()

    # --------------------------------------------------------------- сканирование
    def scan_async(self):
        if self.busy:
            return
        if not self.game or not self.game.found:
            messagebox.showwarning(APP_NAME, "Сначала найдите игру или укажите папку игры вручную.")
            self.show_page("settings")
            return
        if not self.game.loading_root:
            messagebox.showerror(APP_NAME, "В папке игры не найдена директория игровых ресурсов:\n"
                                           "Data\\Gfx\\UI\\BattleLoadingScreen")
            return
        loading_root = self.game.loading_root
        maps = self.maps
        self._run_bg("Сканирование ресурсов…",
                     lambda: scan_resources(loading_root, maps),
                     self._after_scan)

    def _after_scan(self, result: ScanResult):
        self.scan = result
        self.settings.set("scan", result.to_settings())
        self.settings.save()
        self.refresh_status()
        if result.error:
            self.set_status(result.error)
            messagebox.showerror(APP_NAME, result.error)
        else:
            self.set_status(f"Сканирование завершено: найдено {result.found} из {result.total} карт")

    # ------------------------------------------------------------- изображения
    def choose_image(self):
        if not self.selected_code:
            return
        path = filedialog.askopenfilename(
            title="Выберите загрузочный экран",
            filetypes=[("Изображения", f"*.png *.jpg *.jpeg *.webp *.bmp"), ("Все файлы", "*.*")])
        if not path:
            return
        try:
            info = validate_image(path)
        except ImageError as exc:
            messagebox.showerror(APP_NAME, str(exc))
            return
        try:
            saved = copy_user_image(path, self.settings.custom_images_dir(), self.selected_code)
        except (ImageError, OSError) as exc:
            messagebox.showerror(APP_NAME, f"Не удалось сохранить изображение:\n{exc}")
            return
        assignment = self.settings.assignment(self.selected_code)
        assignment["image"] = str(saved)
        assignment["source_name"] = Path(path).name
        assignment["applied"] = False
        assignment["applied_at"] = ""
        self.settings.save()
        self.refresh_status()
        self.set_status(f"Изображение назначено: {info.text} · {info.format}")

    def remove_image(self):
        code = self.selected_code
        if not code:
            return
        assignment = self._assignment(code)
        if not assignment.get("image"):
            return
        if not messagebox.askyesno(APP_NAME, "Удалить назначенное изображение?\n\n"
                                             "Если карта уже изменена в игре, вернуть оригинал можно кнопкой "
                                             "«Сбросить к оригиналу»."):
            return
        path = Path(assignment.get("image", ""))
        self.settings.assignments.pop(code, None)
        self.settings.save()
        if path.is_file() and path.parent == self.settings.custom_images_dir():
            try:
                path.unlink()
            except OSError:
                pass
        self.refresh_status()
        self.set_status("Изображение удалено")

    def reset_map(self):
        code = self.selected_code
        if not code:
            return
        item = get_map(self.maps, code)
        if not item:
            return
        if self.backups.has_backup(code):
            if not messagebox.askyesno(APP_NAME, f"Вернуть оригинальный загрузочный экран карты «{item['name']}»?"):
                return
            self._run_bg("Восстановление оригинала…",
                         lambda: restore_map(code, self.backups),
                         lambda _res: self._after_reset(code))
        else:
            assignment = self._assignment(code)
            if assignment.get("applied"):
                messagebox.showwarning(
                    APP_NAME,
                    "Резервная копия для этой карты не найдена (возможно, резервное копирование "
                    "было отключено). Автоматически вернуть оригинал нельзя — восстановите файлы "
                    "игры через Lesta Game Center.")
                return
            image = Path(assignment.get("image", ""))
            self.settings.assignments.pop(code, None)
            self.settings.save()
            if image.is_file() and image.parent == self.settings.custom_images_dir():
                try:
                    image.unlink()
                except OSError:
                    pass
            self.refresh_status()
            self.set_status("Назначение сброшено (оригинал не изменялся)")

    def _after_reset(self, code: str):
        self.settings.assignments.pop(code, None)
        self.settings.save()
        self.refresh_status()
        self.set_status("Оригинальный загрузочный экран восстановлен")

    # -------------------------------------------------------------- применение
    def _check_ready(self, code: str) -> tuple[dict, MapResource, str] | None:
        item = get_map(self.maps, code)
        if not item:
            return None
        assignment = self._assignment(code)
        image = assignment.get("image", "")
        if not image or not Path(image).is_file():
            messagebox.showwarning(APP_NAME, "Сначала выберите изображение для этой карты.")
            return None
        res = self._scan_map(code)
        if not res or not res.found:
            messagebox.showwarning(APP_NAME, "Загрузочный экран этой карты не найден в ресурсах игры.\n"
                                             "Выполните сканирование после обновления игры.")
            return None
        return item, res, image

    def apply_selected(self):
        code = self.selected_code
        if not code:
            return
        ready = self._check_ready(code)
        if not ready:
            return
        item, res, image = ready
        if self.settings.get("confirm_apply", True):
            if not messagebox.askyesno(
                    APP_NAME,
                    f"Применить изображение к карте «{item['name']}»?\n\n"
                    f"Будет заменено файлов: {len(res.files)} (базовый экран и модификации).\n"
                    "Перед заменой будет создана резервная копия."):
                return
        quality = int(self.settings.get("quality", 90))
        crop = self.settings.get("crop_mode", "cover")
        use_backup = bool(self.settings.get("backup_enabled", True))
        self._run_bg(
            f"Применение: {item['name']}…",
            lambda: apply_map(item, image, res, self.backups, quality, crop, use_backup),
            lambda result: self._after_apply(result),
        )

    def _after_apply(self, result: dict):
        code = result["code"]
        assignment = self.settings.assignment(code)
        assignment["applied"] = True
        assignment["applied_at"] = result["applied_at"]
        assignment["files"] = result["files"]
        assignment["target_size"] = list(result["target_size"])
        self.settings.save()
        self.refresh_status()
        self.set_status(f"Применено: {result['map']} ({len(result['files'])} файл.)")
        messagebox.showinfo(APP_NAME, f"Изображение применено.\n\n"
                                      f"Карта: {result['map']}\n"
                                      f"Файлов заменено: {len(result['files'])}\n\n"
                                      "Запустите игру — изображение появится при загрузке этой карты.")

    def apply_all(self):
        if self.busy:
            return
        if not self.scan:
            messagebox.showwarning(APP_NAME, "Сначала выполните сканирование ресурсов.")
            return
        pending = []
        for item in self.maps:
            code = item["code"]
            assignment = self._assignment(code)
            image = assignment.get("image", "")
            res = self._scan_map(code)
            if image and Path(image).is_file() and res and res.found:
                pending.append((item, res, image))
        if not pending:
            messagebox.showinfo(APP_NAME, "Нет карт, готовых к применению.\n"
                                          "Назначьте изображения картам на вкладке «Карты».")
            return
        if not messagebox.askyesno(APP_NAME, f"Применить изменения для {len(pending)} карт?\n\n"
                                             "Перед заменой будут созданы резервные копии."):
            return
        quality = int(self.settings.get("quality", 90))
        crop = self.settings.get("crop_mode", "cover")
        use_backup = bool(self.settings.get("backup_enabled", True))

        def work():
            results, errors = [], []
            for item, res, image in pending:
                try:
                    results.append(apply_map(item, image, res, self.backups, quality, crop, use_backup))
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{item['name']}: {exc}")
            return results, errors

        self._run_bg("Применение изменений…", work, self._after_apply_all)

    def _after_apply_all(self, payload):
        results, errors = payload
        for result in results:
            assignment = self.settings.assignment(result["code"])
            assignment["applied"] = True
            assignment["applied_at"] = result["applied_at"]
            assignment["files"] = result["files"]
            assignment["target_size"] = list(result["target_size"])
        self.settings.save()
        self.refresh_status()
        message = f"Применено карт: {len(results)}."
        if errors:
            message += "\n\nОшибки:\n• " + "\n• ".join(errors)
        self.set_status(message.replace("\n", " "))
        if errors:
            messagebox.showwarning(APP_NAME, message)
        else:
            messagebox.showinfo(APP_NAME, message)

    # ------------------------------------------------------------ резервные копии
    def refresh_backups(self):
        for row in self.backup_tree.get_children():
            self.backup_tree.delete(row)
        for item in self.backups.all_items():
            self.backup_tree.insert("", "end", iid=item["code"], values=(
                item["map"], item["files"], human_size(item["size"]),
                human_time(item["created_at"])))

    def _selected_backup_code(self) -> str | None:
        selection = self.backup_tree.selection()
        if not selection:
            messagebox.showinfo(APP_NAME, "Выберите карту в списке резервных копий.")
            return None
        return selection[0]

    def restore_selected_backup(self):
        code = self._selected_backup_code()
        if not code:
            return
        item = get_map(self.maps, code)
        name = item["name"] if item else code
        if not messagebox.askyesno(APP_NAME, f"Восстановить оригинальный загрузочный экран карты «{name}»?"):
            return
        self._run_bg("Восстановление…", lambda: restore_map(code, self.backups),
                     lambda _r: self._after_backup_restore([code]))

    def restore_all_backups(self):
        if not self.backups.all_items():
            messagebox.showinfo(APP_NAME, "Резервных копий пока нет.")
            return
        if not messagebox.askyesno(APP_NAME, "Восстановить оригинальные изображения для всех карт?\n\n"
                                             "Текущие изменения будут отменены."):
            return

        def work():
            result = restore_all(self.backups)
            return result

        def done(result):
            codes = [item["code"] for item in self.backups.all_items()]
            self._after_backup_restore(codes, result)

        self._run_bg("Восстановление всех карт…", work, done)

    def _after_backup_restore(self, codes: list[str], result: dict | None = None):
        for code in codes:
            assignment = self.settings.assignments.get(code)
            if assignment:
                assignment["applied"] = False
                assignment["applied_at"] = ""
                assignment.pop("files", None)
        self.settings.save()
        self.refresh_status()
        self.refresh_backups()
        if result and result.get("errors"):
            messagebox.showwarning(APP_NAME, "Восстановлено файлов: %d\n\nОшибки:\n• %s"
                                   % (result.get("restored", 0), "\n• ".join(result["errors"])))
        else:
            self.set_status("Оригинальные изображения восстановлены")
            messagebox.showinfo(APP_NAME, "Оригинальные изображения восстановлены.")

    # ---------------------------------------------------------------- настройки
    def save_settings(self):
        self.settings.set("quality", int(self.quality_var.get()))
        self.settings.set("crop_mode", self.crop_var.get())
        self.settings.set("backup_enabled", bool(self.backup_var.get()))
        self.settings.set("confirm_apply", bool(self.confirm_var.get()))
        entered = self.settings_game_var.get().strip()
        changed = entered and entered != self.settings.get("game_root", "")
        if entered:
            info = validate_game_root(entered)
            if not info:
                messagebox.showerror(APP_NAME, "Указанная папка не содержит tanksblitz.exe и папку Data.")
                return
            info.source = "Указано вручную"
            self._set_game(info)
            if changed:
                self.scan_async()
        self.settings.save()
        self.refresh_status()
        messagebox.showinfo(APP_NAME, "Настройки сохранены.")

    def open_data_folder(self):
        try:
            os.startfile(user_data_dir())
        except (AttributeError, OSError) as exc:
            messagebox.showinfo(APP_NAME, f"Папка данных:\n{user_data_dir()}\n\n{exc}")

    def open_logs_folder(self):
        try:
            os.startfile(self.settings.logs_dir())
        except (AttributeError, OSError) as exc:
            messagebox.showinfo(APP_NAME, f"Папка логов:\n{self.settings.logs_dir()}\n\n{exc}")

    # ------------------------------------------------------------------ потоки
    def _run_bg(self, label: str, func, on_done):
        if self.busy:
            return
        self.busy = True
        self.set_status(label)
        self._bg_callback = on_done
        result_queue: queue.Queue = queue.Queue()

        def worker():
            try:
                result_queue.put(("ok", func()))
            except Exception as exc:  # noqa: BLE001
                LOG.exception("Ошибка фоновой операции: %s", exc)
                result_queue.put(("error", exc))

        threading.Thread(target=worker, daemon=True).start()
        self._poll_bg(result_queue)

    def _poll_bg(self, result_queue: "queue.Queue"):
        try:
            if not self.root.winfo_exists():
                return
            kind, payload = result_queue.get_nowait()
        except queue.Empty:
            try:
                self.root.after(50, lambda: self._poll_bg(result_queue))
            except tk.TclError:
                pass
            return
        except tk.TclError:
            return
        self.busy = False
        if kind == "ok":
            self._bg_done(payload, self._bg_callback)
        else:
            self._bg_error(payload)

    def _bg_done(self, result, on_done):
        self.busy = False
        try:
            on_done(result)
        except Exception as exc:  # noqa: BLE001
            LOG.exception("Ошибка обработки результата: %s", exc)
            messagebox.showerror(APP_NAME, f"Ошибка: {exc}")

    def _bg_error(self, exc: Exception):
        self.busy = False
        self.set_status("Ошибка")
        if isinstance(exc, (ApplyError, ImageError)):
            messagebox.showerror(APP_NAME, str(exc))
        else:
            messagebox.showerror(APP_NAME, f"Произошла ошибка:\n{exc}\n\nПодробности в журнале logs.")

    # ------------------------------------------------------------------ закрытие
    def _restore_geometry(self):
        geometry = self.settings.get("window_geometry", "")
        if geometry:
            try:
                self.root.geometry(geometry)
            except tk.TclError:
                pass

    def on_close(self):
        try:
            self.settings.set("window_geometry", self.root.geometry())
            self.settings.save()
        except Exception:  # noqa: BLE001
            pass
        self.root.destroy()


def run():
    root = tk.Tk()
    BlitzApp(root)
    root.mainloop()
