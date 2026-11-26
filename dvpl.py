"""Формат DVPL (Lesta) — чтение и запись.

Структура файла:
    [полезная нагрузка][original_size u32][compressed_size u32][crc32 u32][type u32]["DVPL"]

type 0 — без сжатия, type 1/2 — LZ4-блок.
Проверено на Tanks Blitz 26.12.0: загрузочные экраны хранятся как type 0,
внутри — обычный WebP (1024x1024).
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

MAGIC = b"DVPL"
HEADER_SIZE = 20
TYPE_STORED = 0
TYPE_LZ4 = 2


class DvplError(Exception):
    pass


def lz4_block_decompress(src: bytes, dest_size: int) -> bytes:
    """Чистый Python-декодер LZ4 block (без внешних зависимостей)."""
    dst = bytearray(dest_size)
    si = 0
    di = 0
    n = len(src)
    while si < n:
        token = src[si]
        si += 1

        literal_len = token >> 4
        if literal_len == 15:
            while True:
                if si >= n:
                    raise DvplError("Повреждённые данные LZ4 (литералы)")
                b = src[si]
                si += 1
                literal_len += b
                if b != 255:
                    break
        if literal_len:
            if si + literal_len > n or di + literal_len > dest_size:
                raise DvplError("Повреждённые данные LZ4 (переполнение)")
            dst[di:di + literal_len] = src[si:si + literal_len]
            si += literal_len
            di += literal_len

        if si >= n:
            break

        if si + 2 > n:
            raise DvplError("Повреждённые данные LZ4 (смещение)")
        offset = src[si] | (src[si + 1] << 8)
        si += 2
        if offset == 0 or offset > di:
            raise DvplError("Повреждённые данные LZ4 (некорректное смещение)")

        match_len = token & 0x0F
        if match_len == 15:
            while True:
                if si >= n:
                    raise DvplError("Повреждённые данные LZ4 (длина совпадения)")
                b = src[si]
                si += 1
                match_len += b
                if b != 255:
                    break
        match_len += 4
        if di + match_len > dest_size:
            raise DvplError("Повреждённые данные LZ4 (переполнение совпадения)")

        start = di - offset
        for i in range(match_len):
            dst[di] = dst[start + i]
            di += 1

    if di != dest_size:
        raise DvplError(f"Размер после распаковки {di} != ожидаемого {dest_size}")
    return bytes(dst)


def parse_dvpl(data: bytes) -> tuple[bytes, dict]:
    if len(data) < HEADER_SIZE or data[-4:] != MAGIC:
        raise DvplError("Файл не является контейнером DVPL")
    original_size, compressed_size, crc, typ = struct.unpack("<IIII", data[-HEADER_SIZE:-4])
    payload = data[:-HEADER_SIZE]
    if len(payload) != compressed_size:
        raise DvplError("Размер полезной нагрузки не совпадает с заголовком")
    if (zlib.crc32(payload) & 0xFFFFFFFF) != crc:
        raise DvplError("CRC32 не совпадает — файл повреждён")
    if typ == TYPE_STORED:
        unpacked = payload
    elif typ in (1, TYPE_LZ4):
        unpacked = lz4_block_decompress(payload, original_size)
    else:
        raise DvplError(f"Неизвестный тип сжатия DVPL: {typ}")
    if len(unpacked) != original_size:
        raise DvplError("Размер распакованных данных не совпадает")
    meta = {
        "original_size": original_size,
        "compressed_size": compressed_size,
        "crc32": crc,
        "type": typ,
    }
    return unpacked, meta


def read_dvpl(path: str | Path) -> tuple[bytes, dict]:
    with open(path, "rb") as f:
        return parse_dvpl(f.read())


def is_dvpl(path: str | Path) -> bool:
    try:
        with open(path, "rb") as f:
            f.seek(-4, 2)
            return f.read(4) == MAGIC
    except OSError:
        return False


def build_dvpl(payload: bytes, compress: bool = False) -> bytes:
    """Собирает DVPL. По умолчанию без сжатия (type 0) — игра это принимает."""
    if compress:
        raise DvplError("Сжатие при записи не поддерживается (используется type 0)")
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    footer = struct.pack("<IIII", len(payload), len(payload), crc, TYPE_STORED) + MAGIC
    return payload + footer
