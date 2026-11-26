"""Каталог карт классического режима 7x7 Tanks Blitz.

Соответствие «русское название -> код ресурсов» получено из официальной
локализации игры (Data/Strings/ru.yaml, ключи #maps:<код>:<сцена>).
В каталог включены только 33 карты из утверждённого ТЗ; событийные,
временные и специальные карты исключены.
"""
from __future__ import annotations

import json
from pathlib import Path

CATALOG_VERSION = 1

# code — ключ карты в maps.yaml игры; variants — все каталоги загрузочных
# экранов этой карты (базовый + модификации), которые нужно заменять вместе.
DEFAULT_MAPS: list[dict] = [
    {"code": "cybermap",     "name": "Стадион",            "variants": ["cybermap"]},
    {"code": "lumber",       "name": "Альпенштадт",        "variants": ["lumber", "lumber_01"]},
    {"code": "karelia",      "name": "Балтийский щит",     "variants": ["karelia"]},
    {"code": "italy",        "name": "Виноградники",       "variants": ["italy"]},
    {"code": "milbase",      "name": "Восточная гавань",   "variants": ["milbase", "milbase_02", "milbase_03", "milbase_04", "milbase_05"]},
    {"code": "savanna",      "name": "Горящие пески",      "variants": ["savanna"]},
    {"code": "rock",         "name": "Древние пирамиды",   "variants": ["rock"]},
    {"code": "grossberg",    "name": "Жемчужный город",    "variants": ["grossberg"]},
    {"code": "malinovka",    "name": "Зимняя Малиновка",   "variants": ["malinovka"]},
    {"code": "mountain",     "name": "Золотая долина",     "variants": ["mountain"]},
    {"code": "canal",        "name": "Канал",              "variants": ["canal", "canal_01"]},
    {"code": "canyon",       "name": "Каньон",             "variants": ["canyon"]},
    {"code": "karieri",      "name": "Карьеры",            "variants": ["karieri"]},
    {"code": "pliego",       "name": "Кастилья",           "variants": ["pliego"]},
    {"code": "lagoon",       "name": "Лагуна",             "variants": ["lagoon"]},
    {"code": "glacier",      "name": "Ледники",            "variants": ["glacier", "glacier_02", "glacier_03"]},
    {"code": "erlenberg",    "name": "Миддлбург",          "variants": ["erlenberg", "erlenberg_01", "erlenberg_02"]},
    {"code": "holland",      "name": "Молендейк",          "variants": ["holland"]},
    {"code": "skit",         "name": "Морской рубеж",      "variants": ["skit"]},
    {"code": "neptune",      "name": "Нормандия",          "variants": ["neptune", "neptune_01", "neptune_02"]},
    {"code": "forgecity",    "name": "Нью-Бэй",            "variants": ["forgecity"]},
    {"code": "port",         "name": "Порт",               "variants": ["port"]},
    {"code": "plant",        "name": "Промзона",           "variants": ["plant"]},
    {"code": "amigosville",  "name": "Протока",            "variants": ["amigosville", "amigosville_02", "amigosville_03"]},
    {"code": "rudniki",      "name": "Рудники",            "variants": ["rudniki", "rudniki_01", "rudniki_02", "rudniki_03"]},
    {"code": "faust",        "name": "Фауст",              "variants": ["faust"]},
    {"code": "fort",         "name": "Форт",               "variants": ["fort"]},
    {"code": "himmelsdorf",  "name": "Химмельсдорф",       "variants": ["himmelsdorf", "himmelsdorf_02", "himmelsdorf_03", "himmelsdorf_04"]},
    {"code": "rift",         "name": "Эллада",             "variants": ["rift"]},
    {"code": "desert_train", "name": "Эль-Аламейн",        "variants": ["desert_train", "desert_train_02", "desert_train_03"]},
    {"code": "medvedkovo",   "name": "Эшелон",             "variants": ["medvedkovo", "medvedkovo_02", "medvedkovo_03"]},
    {"code": "idle",         "name": "Юкон",               "variants": ["idle"]},
    {"code": "mars",         "name": "ПЭПТ",               "variants": ["mars", "mars_02", "mars_03"]},
]

# Имена файлов загрузочного экрана, которые встречаются в ресурсах.
LOADING_FILENAMES = [
    "BackgroundLoading.packed.webp.dvpl",
    "BackgroundLoading.packed.webp",
    "BackgroundLoading.webp.dvpl",
    "BackgroundLoading.webp",
    "BackgroundLoading.dvpl",
    "BackgroundLoading.png",
    "BackgroundLoading.jpg",
]


def default_catalog() -> list[dict]:
    return [dict(item, variants=list(item["variants"])) for item in DEFAULT_MAPS]


def _normalize(items) -> list[dict]:
    result: list[dict] = []
    seen: set[str] = set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code", "")).strip().lower()
        name = str(item.get("name", "")).strip()
        if not code or not name or code in seen:
            continue
        variants = item.get("variants") or [code]
        variants = [str(v).strip().lower() for v in variants if str(v).strip()]
        if code not in variants:
            variants.insert(0, code)
        result.append({"code": code, "name": name, "variants": variants})
        seen.add(code)
    return result


def load_catalog(path: Path) -> list[dict]:
    """Читает maps.json. При отсутствии/ошибке создаёт его из встроенного каталога."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("maps", [])
        maps = _normalize(data)
        if maps:
            # Добавляем карты, появившиеся в новой версии программы
            existing = {m["code"] for m in maps}
            added = [item for item in DEFAULT_MAPS if item["code"] not in existing]
            for item in added:
                maps.append(dict(item, variants=list(item["variants"])))
            if added:
                save_catalog(path, maps)
            return maps
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    maps = default_catalog()
    save_catalog(path, maps)
    return maps


def save_catalog(path: Path, maps: list[dict]) -> None:
    from utils import atomic_write_text
    payload = {
        "version": CATALOG_VERSION,
        "note": "Каталог карт классического режима 7x7. Можно дополнять вручную.",
        "maps": maps,
    }
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def get_map(maps: list[dict], code: str) -> dict | None:
    for item in maps:
        if item["code"] == code:
            return item
    return None
