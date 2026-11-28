"""Индекс игровых изображений по категориям.

Назначение: найти ресурсы, которые можно безопасно заменить, и отделить их от
файлов с неизвестным форматом. Безопасным считается DVPL типа 0 (без сжатия),
внутри которого лежит WebP/PNG/JPEG: такой файл собирается обратно тем же
способом, что и загрузочные экраны (см. dvpl.build_dvpl).

Файлы типа 2 (LZ4) и всё с нераспознанной нагрузкой в индекс не попадают —
их приложение не изменяет (ТЗ, разделы 6 и 13).
"""
from __future__ import annotations

import struct
import time
from pathlib import Path

from PIL import Image

from resource_scanner import MapResource

HEADER_SIZE = 20
TYPE_STORED = 0

# Категория -> папки относительно Data, которые в неё входят.
CATEGORY_ROOTS: dict[str, list[str]] = {
    "garage": ["Gfx/UI/Hangar", "Gfx/Lobby"],
    "flags": ["Gfx/Lobby/flags"],
    "elements": [
        "Gfx/UI/CommonUIElements",
        "Gfx/UI/LobbyCommon",
        "Gfx/UI/InventoryIcons",
        "Gfx/UI/BigTankIcons",
        "Gfx/UI/StorageItemIcons",
    ],
}

CATEGORY_TITLES = {"garage": "Ангар", "elements": "Элементы интерфейса",
                   "profile": "Фоны профиля", "flags": "Флаги",
                   "camos": "Камуфляжи"}

# Фоны профиля игра скачивает в кэш обычными WebP (без DVPL).
# Все они одного формата — 2048×1536; остальное в кэше это баннеры и товары.
CACHE_CATEGORY = "profile"
BACKGROUND_SIZE = (2048, 1536)
CACHE_MIN_SIDE = 700
CACHE_MIN_BYTES = 12_000

COUNTRY_TITLES = {
    "australia": "Австралия", "canada": "Канада", "china": "Китай",
    "czech": "Чехия", "european": "Европа", "finland": "Финляндия",
    "france": "Франция", "germany": "Германия", "gold": "Золотой",
    "italy": "Италия", "japan": "Япония", "other": "Другой",
    "poland": "Польша", "sweden": "Швеция", "uk": "Великобритания",
    "usa": "США", "ussr": "СССР",
}

MAX_PER_ROOT = 2000


def payload_kind(head: bytes) -> str | None:
    """Формат изображения по первым байтам полезной нагрузки."""
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "WEBP"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG"
    if head[:2] == b"\xff\xd8":
        return "JPEG"
    return None


def read_entry(path: Path) -> dict | None:
    """Читает заголовок DVPL и возвращает описание ресурса, если он безопасен."""
    try:
        size = path.stat().st_size
        if size < HEADER_SIZE + 12:
            return None
        with open(path, "rb") as handle:
            head = handle.read(12)
            handle.seek(-HEADER_SIZE, 2)
            footer = handle.read(HEADER_SIZE)
    except OSError:
        return None
    if len(footer) != HEADER_SIZE or footer[-4:] != b"DVPL":
        return None
    _, compressed_size, _, typ = struct.unpack("<IIII", footer[:-4])
    if typ != TYPE_STORED or compressed_size != size - HEADER_SIZE:
        return None
    kind = payload_kind(head)
    if kind is None:
        return None
    return {"format": kind, "size": size}


def flag_country(relative: str) -> str:
    """Страна флага из имени файла: flag_carousel_usa -> usa."""
    stem = relative.split("/")[-1].lower()
    for suffix in (".dvpl", ".packed", ".webp", "@2x", "@3x"):
        stem = stem.replace(suffix, "")
    parts = [part for part in stem.split("_") if part and part != "flag"]
    rest = parts[1:] if parts else []
    while rest and rest[0] in {"i", "ii", "iii", "a", "b"}:
        rest.pop(0)
    return (rest[-1] if rest else (parts[0] if parts else "")).lower()


def pretty_name(stem: str) -> str:
    """«hangar_background_01.packed.webp» -> «hangar background 01»."""
    text = stem
    for suffix in (".dvpl", ".packed", ".webp", ".png", ".jpg", ".jpeg", ".bmp",
                   "@2x", "@3x"):
        text = text.replace(suffix, "").replace(suffix.upper(), "")
    return text.replace("_", " ").replace("-", " ").strip()


def scan_category(data_dir: Path, category: str, roots: list[str],
                  limit: int = MAX_PER_ROOT) -> list[dict]:
    items: list[dict] = []
    for relative in roots:
        root = data_dir / relative
        if not root.is_dir():
            continue
        found = 0
        for path in root.rglob("*.dvpl"):
            if found >= limit:
                break
            info = read_entry(path)
            if info is None:
                continue
            try:
                rel = path.relative_to(data_dir).as_posix()
            except ValueError:
                continue
            items.append({
                "id": rel.lower(),
                "category": category,
                "name": pretty_name(path.stem),
                "path": str(path),
                "rel": rel,
                "size": info["size"],
                "format": info["format"],
                "mtime": path.stat().st_mtime,
            })
            found += 1
    return items


def webp_dimensions(path: Path) -> tuple[int, int] | None:
    """Размер WebP из заголовка — без декодирования картинки.

    Открывать тысячи файлов через Pillow слишком дорого: чтение 40 байт
    даёт тот же результат в сотни раз быстрее.
    """
    try:
        with open(path, "rb") as handle:
            data = handle.read(40)
    except OSError:
        return None
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    chunk = data[12:16]
    if chunk == b"VP8X":
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return width, height
    if chunk == b"VP8 ":
        if data[23:26] != b"\x9d\x01\x2a":
            return None
        width = int.from_bytes(data[26:28], "little") & 0x3FFF
        height = int.from_bytes(data[28:30], "little") & 0x3FFF
        return width, height
    if chunk == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    return None


def scan_cache(cache_dir: str | Path, limit: int = 800) -> list[dict]:
    """Индексирует скачанные изображения из кэша игры.

    Кэш — общая свалка: там и фоны профиля, и баннеры магазина, и картинки
    товаров. Фоном профиля считаем крупный непрозрачный кадр с нормальными
    пропорциями; широкие полосы и картинки с прозрачностью уходят в «Прочие».
    """
    directory = Path(cache_dir)
    if not directory.is_dir():
        return []
    items: list[dict] = []
    paths = sorted(directory.glob("*.webp"),
                   key=lambda path: path.stat().st_mtime, reverse=True)
    for path in paths:
        if len(items) >= limit:
            break
        size_bytes = path.stat().st_size
        dimensions = webp_dimensions(path)
        if dimensions is None:
            try:
                with Image.open(path) as image:
                    dimensions = image.size
            except (OSError, ValueError):
                continue
        width, height = dimensions
        is_background = (width, height) == BACKGROUND_SIZE
        if max(width, height) < CACHE_MIN_SIDE or size_bytes < CACHE_MIN_BYTES:
            continue
        category = CACHE_CATEGORY if is_background else "other"
        items.append({
            "id": f"cache_{path.name.lower()}",
            "category": category,
            "name": (f"Фон профиля · {path.stem[-4:]}" if is_background
                     else f"изображение {width}×{height}"),
            "path": str(path),
            "rel": path.name,
            "size": size_bytes,
            "format": "WEBP",
            "mtime": path.stat().st_mtime,
            "width": width,
            "height": height,
        })
    return items


def _prepare_flags(items: list[dict]) -> list[dict]:
    """Оставляет только настоящие страны, служебные картинки уводит в «Прочие»."""
    result = []
    for item in items:
        country = flag_country(item["rel"])
        if country in COUNTRY_TITLES:
            item["country"] = country
            item["name"] = f"Флаг · {COUNTRY_TITLES[country]}"
        else:
            item["category"] = "other"
        result.append(item)
    return result


CAMO_ROOT = "3d/Tanks/Camouflages"
CAMO_CATEGORY = "camos"


def camo_base_name(filename: str) -> str:
    """«common_01_BC.dx11.dds.dvpl» -> «common_01»."""
    name = filename.lower()
    for suffix in (".dvpl", ".packed.webp", ".packed", ".webp"):
        name = name.replace(suffix, "")
    name = name.replace(".dx11.dds", "").replace(".dds", "")
    if name.endswith("_bc"):
        name = name[:-3]
    return name


CAMO_XML = "XML/item_defs/vehicles/common/camouflages.xml.dvpl"
CAMO_SKIN = "Gfx/UI/CamouflagesShop/Skin"


def _norm_token(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def camo_icon_map(data_dir: Path) -> dict[str, str]:
    """Камуфляж → имя картинки-иконки из camouflages.xml (тег <icon>)."""
    path = data_dir / CAMO_XML
    if not path.is_file():
        return {}
    try:
        from dvpl import read_dvpl
        payload, _ = read_dvpl(path)
        text = payload.decode("utf-8", "ignore")
    except Exception:
        return {}
    import re
    mapping: dict[str, str] = {}
    for name, _id, body in re.findall(
            r"<([a-zA-Z0-9_\-]+)>\s*\n\s*<id>(\d+)</id>(.*?)</\1>", text, re.S):
        icon = re.search(r"<icon>([^<]+)</icon>", body)
        if not icon:
            continue
        stem = icon.group(1).replace("~res:/", "").split("/")[-1]
        if stem.endswith(".txt"):
            stem = stem[:-4]
        mapping[_norm_token(name)] = stem
    return mapping

def scan_camos(data_dir: Path) -> list[dict]:
    """Камуфляжи: карточка на имя, все варианты (основная + _BC + нации) внутри.

    Размер DDS на этапе индексации не читаем: файлы сжаты LZ4, распаковывать
    тысячу с лишним штук при каждом сканировании слишком дорого. Размер
    определяется при применении.
    """
    root = data_dir / CAMO_ROOT
    if not root.is_dir():
        return []
    groups: dict[str, list[dict]] = {}
    for path in root.rglob("*.dvpl"):
        base = camo_base_name(path.name)
        if not base:
            continue
        groups.setdefault(base, []).append({
            "path": str(path),
            "rel": path.relative_to(data_dir).as_posix(),
            "name": path.name,
            "size": path.stat().st_size if path.exists() else 0,
        })
    icons = camo_icon_map(data_dir)
    skin_dir = data_dir / CAMO_SKIN
    items: list[dict] = []
    for base, files in groups.items():
        files.sort(key=lambda entry: entry["path"])
        # иконка вида в списке хранилища — отдельная картинка магазина
        icon_stem = icons.get(_norm_token(base))
        if icon_stem and skin_dir.is_dir():
            for suffix in ("", "@2x"):
                icon_path = skin_dir / f"{icon_stem}{suffix}.packed.webp.dvpl"
                if icon_path.is_file():
                    files.append({
                        "path": str(icon_path),
                        "rel": icon_path.relative_to(data_dir).as_posix(),
                        "name": icon_path.name,
                        "size": icon_path.stat().st_size,
                    })
        primary = files[0]
        items.append({
            "id": f"camo:{base}",
            "category": CAMO_CATEGORY,
            "name": pretty_name(base).capitalize(),
            "path": primary["path"],
            "rel": primary["rel"],
            "size": primary["size"],
            "format": "DDS",
            "mtime": 0,
            "width": 0,
            "height": 0,
            "files": files,
            "variants": len(files),
        })
    return items


def scan_all(data_dir: str | Path) -> list[dict]:
    """Полный проход по категориям. Возвращает список ресурсов без дублей @2x."""
    directory = Path(data_dir)
    items: list[dict] = []
    for category, roots in CATEGORY_ROOTS.items():
        found = scan_category(directory, category, roots)
        if category == "flags":
            found = _prepare_flags(found)
        items.extend(found)
    items.extend(scan_camos(directory))
    return group_variants(items)


SIZE_TOKENS = {"normal", "big", "small", "hires", "lowres", "hd", "sd"}


def _norm_name(relative: str) -> str:
    name = relative.split("/")[-1].lower()
    for suffix in (".dvpl", ".packed", ".webp", ".png", ".jpg", ".jpeg", ".bmp",
                   "@2x", "@3x"):
        name = name.replace(suffix, "")
    return name.replace("_", " ").replace("-", " ").strip()


def _norm_folder(relative: str) -> str:
    parts = relative.lower().split("/")[:-1]
    return "/".join(part for part in parts if part not in SIZE_TOKENS)


def _content_hash(path: str) -> str:
    try:
        import hashlib

        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(262144), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return ""


def group_variants(items: list[dict]) -> list[dict]:
    """Склеивает файлы одного рисунка в одну запись.

    Одинаковым считается ресурс с тем же именем в «той же» папке (папки размеров
    Normal/Big и суффиксы @2x не различают рисунок) либо файл с точно таким же
    содержимым, лежащий в другой папке. Применяются все файлы группы сразу.
    """
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for item in items:
        if item.get("category") == "flags":
            key = f"flags|{item.get('country', _norm_name(item.get('rel', '')))}"
        else:
            key = f"{_norm_folder(item.get('rel', ''))}|{_norm_name(item.get('rel', ''))}"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(item)

    # одинаковые по содержимому группы склеиваем между папками
    by_hash: dict[str, str] = {}
    remap: dict[str, str] = {}
    for key in order:
        group = groups[key]
        base = next((entry for entry in group if "@2x" not in entry["rel"].lower()),
                    group[0])
        digest = _content_hash(base["path"])
        bucket = f"{digest}|{group[0].get('category')}" if digest else ""
        if bucket and bucket in by_hash:
            remap[key] = by_hash[bucket]
        elif bucket:
            by_hash[bucket] = key

    merged_groups: dict[str, list[dict]] = {}
    merged_order: list[str] = []
    for key in order:
        target = remap.get(key, key)
        if target not in merged_groups:
            merged_groups[target] = []
            merged_order.append(target)
        merged_groups[target].extend(groups[key])

    result: list[dict] = []
    for key in merged_order:
        group = merged_groups[key]
        if group and group[0].get("category") == "flags":
            # основным считаем «carousel» — он выглядит как сам флаг
            group = sorted(group, key=lambda entry: (
                0 if "carousel" in entry["rel"].lower() else 1,
                "@2x" in entry["rel"].lower(), entry["rel"]))
        base = next((entry for entry in group if "@2x" not in entry["rel"].lower()),
                    group[0])
        merged = dict(base)
        merged["files"] = [
            {"path": entry["path"], "rel": entry["rel"], "size": entry.get("size", 0),
             "mtime": entry.get("mtime", 0)}
            for entry in sorted(group, key=lambda entry: entry["rel"])
        ]
        merged["variants"] = len(group)
        merged["size"] = sum(entry.get("size", 0) for entry in group)
        result.append(merged)
    return result


def index_payload(items: list[dict]) -> dict:
    return {"version": 1, "scanned_at": time.time(), "items": items}


def load_index(settings_scan: dict | None) -> dict[str, dict]:
    """Индекс из настроек в виде словаря id -> ресурс."""
    result: dict[str, dict] = {}
    for item in (settings_scan or {}).get("items", []):
        if isinstance(item, dict) and item.get("id"):
            result[item["id"]] = item
    return result


def to_map_resource(entry: dict) -> MapResource:
    """Обёртка, чтобы применять замену ресурсов теми же функциями, что и карты."""
    resource = MapResource(code=entry["id"], name=entry["name"])
    files = entry.get("files") or [{
        "path": entry["path"],
        "rel": entry.get("rel", entry["id"]),
        "size": entry.get("size", 0),
        "mtime": entry.get("mtime", 0),
    }]
    resource.found = True
    resource.files = [
        {"variant": item.get("rel", entry["id"]), "path": item["path"],
         "size": item.get("size", 0), "mtime": item.get("mtime", 0)}
        for item in files
    ]
    resource.primary = files[0]["path"]
    return resource
