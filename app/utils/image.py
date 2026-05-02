"""
Z-Core Image Utilities
======================
WebP conversion, thumbnail generation, SEO-friendly renaming.
"""

import hashlib
import os
import re
import unicodedata
from pathlib import Path
from datetime import datetime

from config import settings


def slugify_filename(filename: str) -> str:
    """Convert filename to SEO-friendly format."""
    name, ext = os.path.splitext(filename)
    # Normalize unicode (Vietnamese)
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^\w\s-]", "", name.lower())
    name = re.sub(r"[-\s]+", "-", name).strip("-")
    # Add short hash to prevent collisions
    short_hash = hashlib.md5(filename.encode()).hexdigest()[:6]
    return f"{name}-{short_hash}{ext}"


def get_upload_path(filename: str, subfolder: str = "") -> Path:
    """Generate upload path organized by date."""
    today = datetime.utcnow().strftime("%Y/%m")
    base = settings.UPLOADS_DIR / subfolder / today if subfolder else settings.UPLOADS_DIR / today
    base.mkdir(parents=True, exist_ok=True)
    return base / slugify_filename(filename)


def convert_to_webp(input_path: str, quality: int = None) -> str:
    """Convert image to WebP format. Returns path to WebP file."""
    try:
        from PIL import Image
    except ImportError:
        return input_path  # Pillow not installed, skip conversion

    quality = quality or settings.WEBP_QUALITY
    input_path = Path(input_path)
    webp_path = input_path.with_suffix(".webp")

    try:
        img = Image.open(input_path)
        # Preserve transparency
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
        else:
            img = img.convert("RGB")
        img.save(webp_path, "WEBP", quality=quality, optimize=True)
        return str(webp_path)
    except Exception:
        return str(input_path)  # Return original on failure


def create_thumbnail(input_path: str, max_size: tuple = (400, 400)) -> str:
    """Create a thumbnail for an image."""
    try:
        from PIL import Image
    except ImportError:
        return input_path

    input_path = Path(input_path)
    thumb_path = input_path.parent / f"{input_path.stem}-thumb{input_path.suffix}"

    try:
        img = Image.open(input_path)
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        img.save(thumb_path, quality=85, optimize=True)
        return str(thumb_path)
    except Exception:
        return str(input_path)


def get_image_dimensions(file_path: str) -> tuple:
    """Get image width and height."""
    try:
        from PIL import Image
        img = Image.open(file_path)
        return img.size  # (width, height)
    except Exception:
        return (0, 0)
