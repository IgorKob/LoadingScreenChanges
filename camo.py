"""Камуфляжи: DDS-текстуры внутри DVPL.

Камуфляж в игре — сетка, которая накладывается на любую модель танка, поэтому
одно имя файла встречается у нескольких наций и в двух вариантах: основная
текстура и такая же с суффиксом `_BC` (PBR). Менять их нужно вместе.

Конвертацию в DDS и обратно делает texconv из пакета Microsoft DirectXTex:
Pillow такие текстуры не читает и не пишет.
"""
from __future__ import annotations

import hashlib
import shutil
import sys
import struct
import subprocess
from contextlib import contextmanager
from pathlib import Path

import utils
from dvpl import parse_dvpl, read_dvpl

MAGIC = b"DDS "
HEADER_SIZE = 128

# форматы, которые понимает texconv и которые встречаются в игре
FOURCC_BC1 = b"DXT1"
FOURCC_BC3 = b"DXT5"


def texconv_path() -> Path:
    """Ищет texconv.exe: рядом с exe, в распакованном архиве или в PATH."""
    candidates = [utils.app_dir() / "tools" / "texconv.exe",
                  utils.app_dir() / "texconv.exe"]
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        candidates.append(Path(bundled) / "tools" / "texconv.exe")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    found = shutil.which("texconv")
    return Path(found) if found else Path("texconv.exe")


def available() -> bool:
    """Есть ли чем конвертировать DDS."""
    path = texconv_path()
    return path.is_file() or path.name == "texconv.exe"


def dds_info(payload: bytes) -> dict | None:
    """Размер и формат DDS из заголовка (без декодирования пикселей)."""
    if len(payload) < HEADER_SIZE or not payload.startswith(MAGIC):
        return None
    height, width = struct.unpack("<II", payload[12:20])
    fourcc = payload[84:88]
    return {"width": width, "height": height, "fourcc": fourcc}


def dds_payload(path: Path) -> bytes | None:
    """Достаёт DDS из DVPL-файла камуфляжа."""
    try:
        payload, _meta = read_dvpl(path)
    except Exception:
        return None
    if not payload.startswith(MAGIC):
        return None
    return payload


@contextmanager
def workdir() -> Path:
    """Рабочая папка рядом с данными: во временной песочнице texconv не пишет."""
    folder = utils.user_data_dir() / "camo_tmp"
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True, exist_ok=True)
    try:
        yield folder
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def _run(args: list[str]) -> bool:
    try:
        result = subprocess.run(
            [str(texconv_path())] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def dds_to_png(source: Path, target: Path) -> bool:
    """DDS → PNG для миниатюр и предпросмотра."""
    target.parent.mkdir(parents=True, exist_ok=True)
    return _run(["-nologo", "-y", "-ft", "png", "-o", str(target.parent),
                 "-f", "R8G8B8A8_UNORM", str(source)]) and target.exists()


def image_to_dds(source: Path, width: int, height: int, fourcc: bytes,
                 target_dir: Path) -> Path | None:
    """Любая картинка → DDS нужного размера и формата."""
    fmt = "BC3_UNORM" if fourcc == FOURCC_BC3 else "BC1_UNORM"
    ok = _run(["-nologo", "-y", "-ft", "dds", "-f", fmt,
               "-w", str(width), "-h", str(height), "-m", "1",
               "-o", str(target_dir), str(source)])
    if not ok:
        return None
    produced = target_dir / (source.stem + ".dds")
    return produced if produced.exists() else None


def thumbnail(path: Path, width: int, height: int) -> Path | None:
    """Готовит PNG-миниатюру камуфляжа и кэширует её по содержимому файла."""
    payload = dds_payload(path)
    if payload is None:
        return None
    digest = hashlib.sha1(payload).hexdigest()[:16]
    cache_dir = utils.user_data_dir() / "camo_cache"
    target = cache_dir / f"{digest}.png"
    if target.exists():
        return target
    cache_dir.mkdir(parents=True, exist_ok=True)
    with workdir() as folder:
        work = Path(folder)
        source = work / "input.dds"
        source.write_bytes(payload)
        # texconv сам называет результат по имени исходника
        if not dds_to_png(source, work / "input.png"):
            return None
        produced = work / "input.png"
        if not produced.exists():
            return None
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(produced.read_bytes())
        return target
    return None
