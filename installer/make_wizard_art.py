"""
Generates the installer's wizard artwork.

Inno Setup's "modern" wizard style shows a tall banner on the welcome and
finished pages, plus a small header image on every other page. Both are
generated here rather than hand-drawn, so the installer art always matches
the app icon and the author/version text can never drift out of sync with
`core.config`.

Run via `build.py`; output lands in `installer/art/`.
"""

from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.icon import build_icon  # noqa: E402
from core.config import UI  # noqa: E402

AUTHOR = "Erfan Esmailzadeh"

ART_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "art")

# Inno's nominal sizes; it scales these for high-DPI automatically.
_BANNER_SIZE = (164, 314)
_HEADER_SIZE = (55, 55)

# Rendered at 3x then downscaled, for the same antialiasing reasons as the
# app icon — installer art is very visible and looks cheap if it is soft.
_SS = 3

_GRAD_TOP = (91, 62, 214)
_GRAD_BOTTOM = (28, 20, 66)
_TEXT = (255, 255, 255)
_TEXT_DIM = (188, 178, 235)


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Prefer Segoe UI (ships with Windows); fall back to Pillow's default."""
    candidates = ["segoeuib.ttf", "segoeui.ttf"] if bold else ["segoeui.ttf"]
    for name in candidates:
        try:
            return ImageFont.truetype(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name), size)
        except OSError:
            continue
    return ImageFont.load_default()


def _vertical_gradient(size: tuple[int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for row in range(height):
        blend = row / max(1, height - 1)
        draw.line(
            [(0, row), (width, row)],
            fill=tuple(int(a + (b - a) * blend) for a, b in zip(_GRAD_TOP, _GRAD_BOTTOM)),
        )
    return image


def build_banner() -> Image.Image:
    """The tall welcome/finished-page banner: icon, name, version, author."""
    width, height = _BANNER_SIZE[0] * _SS, _BANNER_SIZE[1] * _SS
    image = _vertical_gradient((width, height)).convert("RGBA")
    draw = ImageDraw.Draw(image)

    icon_size = int(width * 0.52)
    icon = build_icon(size=icon_size)
    image.paste(icon, ((width - icon_size) // 2, int(height * 0.13)), icon)

    def centred(text: str, y: int, font: ImageFont.FreeTypeFont, fill) -> None:
        text_width = draw.textbbox((0, 0), text, font=font)[2]
        draw.text(((width - text_width) // 2, y), text, font=font, fill=fill)

    centred(UI.APP_NAME, int(height * 0.53), _load_font(int(width * 0.14), bold=True), _TEXT)
    centred(f"v{UI.VERSION}", int(height * 0.62), _load_font(int(width * 0.075)), _TEXT_DIM)

    # Author credit pinned to the bottom of the banner, so it is visible on
    # the very first page of the installer.
    centred(AUTHOR, int(height * 0.90), _load_font(int(width * 0.068), bold=True), _TEXT)

    return image.convert("RGB").resize(_BANNER_SIZE, Image.LANCZOS)


def build_header() -> Image.Image:
    """The small per-page header image — just the app icon on the page background."""
    size = _HEADER_SIZE[0] * _SS
    # Inno composites this on the wizard's white header strip.
    image = Image.new("RGB", (size, size), (255, 255, 255))
    icon = build_icon(size=int(size * 0.86))
    offset = (size - icon.width) // 2
    image.paste(icon, (offset, offset), icon)
    return image.resize(_HEADER_SIZE, Image.LANCZOS)


def main() -> None:
    os.makedirs(ART_DIR, exist_ok=True)
    build_banner().save(os.path.join(ART_DIR, "banner.bmp"))
    build_header().save(os.path.join(ART_DIR, "header.bmp"))
    print(f"Wizard art written to {ART_DIR}")


if __name__ == "__main__":
    main()
