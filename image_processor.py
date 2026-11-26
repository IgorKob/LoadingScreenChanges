"""Обработка изображений: проверка, предпросмотр, подготовка под ресурс игры."""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

from dvpl import DvplError, is_dvpl, read_dvpl
from utils import LOG

SUPPORTED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
FORMATS_TEXT = "PNG, JPG/JPEG, WEBP, BMP"
MAX_PIXELS = 120_000_000  # защита от «бомб» декомпрессии


class ImageError(Exception):
    pass


@dataclass
class ImageInfo:
    path: str
    width: int
    height: int
    mode: str
    format: str

    @property
    def aspect(self) -> float:
        return self.width / self.height if self.height else 0.0

    @property
    def text(self) -> str:
        return f"{self.width} × {self.height}"


def validate_image(path: str | Path) -> ImageInfo:
    path = Path(path)
    if not path.is_file():
        raise ImageError(f"Файл не найден: {path}")
    if path.suffix.lower() not in SUPPORTED_EXT:
        raise ImageError(f"Формат не поддерживается. Допустимы: {FORMATS_TEXT}.")
    try:
        with Image.open(path) as img:
            img.verify()
        with Image.open(path) as img:
            width, height = img.size
            if width * height > MAX_PIXELS:
                raise ImageError("Слишком большое изображение.")
            return ImageInfo(str(path), width, height, img.mode, img.format or path.suffix.upper())
    except ImageError:
        raise
    except Exception as exc:
        raise ImageError(f"Не удалось открыть изображение: {exc}") from exc


def load_game_image(path: str | Path) -> Image.Image:
    """Открывает игровой ресурс: DVPL-контейнер или обычный файл."""
    path = Path(path)
    try:
        if is_dvpl(path):
            payload, _ = read_dvpl(path)
            return Image.open(io.BytesIO(payload)).convert("RGB")
        return Image.open(path).convert("RGB")
    except (DvplError, OSError, ValueError) as exc:
        raise ImageError(f"Не удалось прочитать игровое изображение: {exc}") from exc


def game_image_size(path: str | Path) -> tuple[int, int]:
    with load_game_image(path) as img:
        return img.size


def prepare_image_bytes(image_path: str | Path,
                        target_size: tuple[int, int],
                        crop_mode: str = "cover",
                        quality: int = 90) -> tuple[bytes, dict]:
    """Готовит WebP под размер оригинала.

    crop_mode:
      cover   — заполнить кадр с обрезкой лишнего (по умолчанию);
      contain — вписать целиком, поля чёрные;
      stretch — растянуть без сохранения пропорций.
    """
    quality = max(50, min(100, int(quality)))
    path = Path(image_path)
    try:
        with Image.open(path) as src:
            src.load()
            if src.mode not in ("RGB", "RGBA"):
                src = src.convert("RGBA")
            width, height = target_size
            if width <= 0 or height <= 0:
                raise ImageError("Некорректный размер оригинала.")

            if crop_mode == "contain":
                contained = ImageOps.contain(src.convert("RGBA"), (width, height), Image.Resampling.LANCZOS)
                canvas = Image.new("RGBA", (width, height), (0, 0, 0, 255))
                canvas.paste(contained, ((width - contained.width) // 2,
                                         (height - contained.height) // 2),
                             contained)
                prepared = canvas
            elif crop_mode == "stretch":
                prepared = src.convert("RGBA").resize((width, height), Image.Resampling.LANCZOS)
            else:
                prepared = ImageOps.fit(src.convert("RGBA"), (width, height),
                                        method=Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            prepared.save(buffer, format="WEBP", quality=quality, method=6)
            data = buffer.getvalue()
            info = {
                "source_size": src.size,
                "target_size": (width, height),
                "output_size": prepared.size,
                "bytes": len(data),
                "crop_mode": crop_mode,
                "quality": quality,
            }
            LOG.info("Изображение подготовлено: %s -> %s, %d КБ", src.size, prepared.size, len(data) // 1024)
            return data, info
    except ImageError:
        raise
    except Exception as exc:
        raise ImageError(f"Не удалось обработать изображение: {exc}") from exc


def make_preview(image: Image.Image, box: tuple[int, int]) -> Image.Image:
    """Пропорционально вписывает изображение в рамку предпросмотра."""
    return ImageOps.contain(image.convert("RGB"), box, Image.Resampling.LANCZOS)


def copy_user_image(source: str | Path, dest_dir: Path, code: str) -> Path:
    """Копирует пользовательское изображение в custom_images/<code>.<ext>."""
    source = Path(source)
    validate_image(source)
    dest_dir.mkdir(parents=True, exist_ok=True)
    ext = source.suffix.lower()
    if ext == ".jpeg":
        ext = ".jpg"
    dest = dest_dir / f"{code}{ext}"
    # Удаляем прежние файлы этого пользователя с другим расширением
    for old in dest_dir.glob(f"{code}.*"):
        if old != dest:
            try:
                old.unlink()
            except OSError:
                pass
    import shutil
    shutil.copy2(source, dest)
    return dest
