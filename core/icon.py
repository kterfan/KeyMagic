"""
Procedurally drawn application icon.

Design
-------
A 3D extruded **keycap** — a rounded-square top face sitting on a visibly
darker body, so the shape reads as a physical key rather than a flat badge.
It is deliberately not a circle, it is unique to this app, and it is
on-theme: this is a keyboard-layout tool, so its mark is a key.

The top face carries a two-way swap arrow (the actual function: convert
text from one layout to the other).

Everything is generated at runtime with Pillow, so the app ships with no
external image assets and the icon can be recolored per state (active vs.
paused) without maintaining separate files.

Rendering notes
----------------
The whole icon is drawn at 4x the requested size and downscaled with
LANCZOS resampling at the end. Antialiasing quality is what separates a
crisp tray icon from a muddy one at 16-24px, and supersampling gives far
better edges than drawing small directly.
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter

# Supersampling factor — draw big, shrink down, get clean edges.
_SS = 4

# Active palette: indigo -> violet, a saturated modern gradient.
_TOP_LIGHT = (129, 140, 248)     # indigo-400
_TOP_DARK = (109, 40, 217)       # violet-700
_BODY_LIGHT = (79, 70, 229)      # indigo-600
_BODY_DARK = (49, 46, 129)       # indigo-900

# Paused palette: same geometry, drained of color so the state is obvious
# at a glance in the tray without needing a second glyph.
_PAUSED_TOP_LIGHT = (161, 161, 170)
_PAUSED_TOP_DARK = (82, 82, 91)
_PAUSED_BODY_LIGHT = (113, 113, 122)
_PAUSED_BODY_DARK = (63, 63, 70)


def _vertical_gradient(size: int, box, top_color, bottom_color, radius: int) -> Image.Image:
    """
    Return a transparent RGBA canvas containing one rounded rectangle
    filled with a vertical gradient from `top_color` to `bottom_color`.
    """
    x0, y0, x1, y1 = box
    height = max(1, int(y1 - y0))

    # Paint the gradient across the full box, one horizontal line per row.
    gradient = Image.new("RGB", (int(x1 - x0), height))
    painter = ImageDraw.Draw(gradient)
    for row in range(height):
        blend = row / max(1, height - 1)
        painter.line(
            [(0, row), (int(x1 - x0), row)],
            fill=tuple(
                int(top + (bottom - top) * blend)
                for top, bottom in zip(top_color, bottom_color)
            ),
        )

    # Clip it to the rounded-rectangle silhouette.
    mask = Image.new("L", (int(x1 - x0), height), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, int(x1 - x0) - 1, height - 1], radius=radius, fill=255
    )

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(gradient, (int(x0), int(y0)), mask)
    return canvas


def _draw_swap_arrows(draw: ImageDraw.ImageDraw, cx: float, cy: float, scale: float, fill) -> None:
    """
    Draw the two-way swap mark: an arrow pointing right above an arrow
    pointing left. Built from polygons rather than a font glyph so it
    renders identically on every machine, with no font dependency.
    """
    # Proportions are tuned for legibility at 16px, where the tray actually
    # renders this: a thin, delicate glyph turns to mush at that size, so
    # the mark is deliberately chunky.
    span = 104 * scale       # half-width of each arrow
    gap = 60 * scale         # vertical distance between the two arrows
    shaft = 30 * scale       # shaft thickness
    head_w = 52 * scale      # arrowhead length
    head_h = 82 * scale      # arrowhead width

    # Top arrow — pointing right.
    y = cy - gap / 2
    draw.rectangle([cx - span, y - shaft / 2, cx + span - head_w, y + shaft / 2], fill=fill)
    draw.polygon(
        [(cx + span, y), (cx + span - head_w, y - head_h / 2), (cx + span - head_w, y + head_h / 2)],
        fill=fill,
    )

    # Bottom arrow — pointing left.
    y = cy + gap / 2
    draw.rectangle([cx - span + head_w, y - shaft / 2, cx + span, y + shaft / 2], fill=fill)
    draw.polygon(
        [(cx - span, y), (cx - span + head_w, y - head_h / 2), (cx - span + head_w, y + head_h / 2)],
        fill=fill,
    )


def build_icon(paused: bool = False, size: int = 256) -> Image.Image:
    """
    Render the application icon at `size` x `size` pixels.

    `paused=True` returns the desaturated variant used while hotkeys are
    disabled, so the tray reflects app state without a separate badge.
    """
    canvas_size = size * _SS
    top_light, top_dark, body_light, body_dark = (
        (_PAUSED_TOP_LIGHT, _PAUSED_TOP_DARK, _PAUSED_BODY_LIGHT, _PAUSED_BODY_DARK)
        if paused
        else (_TOP_LIGHT, _TOP_DARK, _BODY_LIGHT, _BODY_DARK)
    )

    image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))

    # Margins are kept tight: a tray icon is only ~16px, so every pixel
    # spent on empty padding is a pixel taken from the readable mark.
    pad = canvas_size * 0.055         # outer margin
    depth = canvas_size * 0.10        # extrusion height — the "3D" part
    inset = canvas_size * 0.020       # top face narrower than body -> perspective
    radius_body = int(canvas_size * 0.21)
    radius_top = int(canvas_size * 0.18)

    # --- Contact shadow, so the key sits on the surface rather than floating.
    shadow = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [pad * 1.4, pad + depth * 1.6, canvas_size - pad * 1.4, canvas_size - pad * 0.35],
        radius=radius_body,
        fill=(15, 15, 40, 115),
    )
    image = Image.alpha_composite(image, shadow.filter(ImageFilter.GaussianBlur(canvas_size * 0.025)))

    # --- Key body (the visible sides of the extrusion).
    image = Image.alpha_composite(
        image,
        _vertical_gradient(
            canvas_size,
            (pad, pad + depth, canvas_size - pad, canvas_size - pad),
            body_light,
            body_dark,
            radius_body,
        ),
    )

    # --- Key top face, lifted up by `depth` to reveal the body beneath it.
    top_box = (pad + inset, pad, canvas_size - pad - inset, canvas_size - pad - depth)
    image = Image.alpha_composite(
        image, _vertical_gradient(canvas_size, top_box, top_light, top_dark, radius_top)
    )

    # --- Glossy highlight across the upper half of the top face.
    gloss = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    gloss_draw = ImageDraw.Draw(gloss)
    gloss_draw.rounded_rectangle(
        [top_box[0], top_box[1], top_box[2], top_box[1] + (top_box[3] - top_box[1]) * 0.46],
        radius=radius_top,
        fill=(255, 255, 255, 58),
    )
    image = Image.alpha_composite(image, gloss.filter(ImageFilter.GaussianBlur(canvas_size * 0.012)))

    # --- Bevel: a bright rim along the top edge reads as a lit surface.
    bevel = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    ImageDraw.Draw(bevel).rounded_rectangle(
        list(top_box), radius=radius_top, outline=(255, 255, 255, 96), width=int(canvas_size * 0.008)
    )
    image = Image.alpha_composite(image, bevel)

    # --- Swap glyph, with a soft dark copy behind it for legibility.
    glyph_cx = (top_box[0] + top_box[2]) / 2
    glyph_cy = (top_box[1] + top_box[3]) / 2
    scale = canvas_size / 512

    glyph_shadow = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    _draw_swap_arrows(
        ImageDraw.Draw(glyph_shadow), glyph_cx, glyph_cy + canvas_size * 0.012, scale, (30, 20, 70, 120)
    )
    image = Image.alpha_composite(image, glyph_shadow.filter(ImageFilter.GaussianBlur(canvas_size * 0.01)))

    glyph = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    _draw_swap_arrows(ImageDraw.Draw(glyph), glyph_cx, glyph_cy, scale, (255, 255, 255, 255))
    image = Image.alpha_composite(image, glyph)

    return image.resize((size, size), Image.LANCZOS)


def save_ico(path: str) -> None:
    """
    Write a multi-resolution Windows .ico — useful for PyInstaller builds
    and as the repository's icon asset.
    """
    build_icon(size=256).save(
        path,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
