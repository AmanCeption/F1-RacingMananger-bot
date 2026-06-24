"""
Qualifying Image Generator
Generates a qualifying result card: Pole Hero banner + full grid with Q1/Q2/Q3 times.
Returns PNG bytes ready for bot.send_photo().
"""
import io
import logging
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

_FONT_PATHS = {
    "bold":   "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "normal": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
}


def _font(style: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(_FONT_PATHS[style], size)
    except Exception:
        return ImageFont.load_default()


def _fmt_time(secs: float | None) -> str:
    if secs is None:
        return "—"
    m, s = divmod(secs, 60)
    return f"{int(m)}:{s:06.3f}"


def generate_qualifying_image(
    race_name: str,
    circuit: str,
    weather_label: str,
    grid: list[dict],
) -> bytes:
    """
    Generate qualifying result card PNG.

    grid: list of dicts with keys:
        position (int), driver (str), team (str),
        q1 (float|None), q2 (float|None), q3 (float|None),
        best_time (float|None)

    Returns PNG bytes.
    """
    W      = 860
    HERO_H = 180
    COL_H  = 30
    ROW_H  = 42
    FOOTER = 48
    H = HERO_H + COL_H + ROW_H * len(grid) + FOOTER

    img  = Image.new("RGB", (W, H), (11, 11, 18))
    draw = ImageDraw.Draw(img)

    pole = grid[0] if grid else {}

    # ── Pole Hero Banner ────────────────────────────────────────────────
    for i in range(HERO_H):
        shade = 25 + i // 4
        draw.line([(0, i), (W, i)], fill=(shade, 10, 10))

    draw.rectangle([0, 0, W, 6], fill=(255, 200, 0))
    draw.rectangle([0, HERO_H - 4, W, HERO_H], fill=(230, 0, 0))

    # P1 gold badge
    draw.ellipse([28, 28, 100, 100], fill=(200, 160, 0))
    draw.ellipse([32, 32,  96,  96], fill=(255, 210, 0))
    draw.text((46, 40), "P1", font=_font("bold", 30), fill=(20, 10, 0))

    draw.text((120, 22), "POLE POSITION",   font=_font("bold",   14), fill=(255, 200, 0))
    draw.text((120, 44), pole.get("driver", ""), font=_font("bold", 36), fill=(255, 255, 255))
    draw.text((122, 90), pole.get("team",   ""), font=_font("normal", 18), fill=(200, 200, 220))

    best = pole.get("q3") or pole.get("q2") or pole.get("q1")
    draw.text((120, 118), f"\u23f1  {_fmt_time(best)}", font=_font("bold", 28), fill=(255, 210, 0))

    # Top-right info
    draw.text((W - 340, 22), race_name,      font=_font("bold",   16), fill=(220, 220, 255))
    draw.text((W - 340, 46), circuit,         font=_font("normal", 13), fill=(150, 150, 180))
    draw.text((W - 340, 66), weather_label,   font=_font("normal", 13), fill=(150, 200, 150))

    # ── Column Headers ─────────────────────────────────────────────────
    y = HERO_H + 6
    draw.rectangle([0, y, W, y + COL_H], fill=(20, 20, 35))
    for text, x in [("POS", 18), ("DRIVER", 62), ("TEAM", 310), ("Q1", 530), ("Q2", 638), ("Q3", 746)]:
        draw.text((x, y + 6), text, font=_font("bold", 12), fill=(120, 120, 160))

    y += COL_H
    MEDALS = {1: (255, 215, 0), 2: (192, 192, 192), 3: (205, 127, 50)}

    for entry in grid:
        pos    = entry.get("position", 0)
        q1, q2, q3 = entry.get("q1"), entry.get("q2"), entry.get("q3")

        row_bg = (20, 20, 35) if pos % 2 == 0 else (15, 15, 28)
        draw.rectangle([0, y - 2, W, y + ROW_H - 4], fill=row_bg)

        if pos in MEDALS:
            draw.rectangle([0, y - 2, 5, y + ROW_H - 4], fill=MEDALS[pos])

        pos_color = MEDALS.get(pos, (180, 180, 210))
        draw.text((18,  y + 8), str(pos),                   font=_font("bold",   15), fill=pos_color)
        draw.text((62,  y + 8), entry.get("driver", "")[:22], font=_font("bold",   15), fill=(230, 230, 255))
        draw.text((310, y + 8), entry.get("team",   "")[:22], font=_font("normal", 13), fill=(170, 170, 200))

        # Q1 — grey if driver made Q2/Q3, green if eliminated in Q1
        q1_color = (150, 150, 175) if (q2 or q3) else (100, 200, 100)
        if q3 is not None:
            draw.rectangle([524, y + 4, 560, y + 22], fill=(80, 20, 120))
            draw.text((527, y + 5), "Q3", font=_font("bold", 10), fill=(200, 100, 255))
        draw.text((530, y + 8), _fmt_time(q1), font=_font("normal", 13), fill=q1_color)

        if q2 is not None:
            q2_color = (150, 150, 175) if q3 else (255, 180, 50)
            draw.text((638, y + 8), _fmt_time(q2), font=_font("normal", 13), fill=q2_color)
        else:
            draw.text((638, y + 8), "—", font=_font("normal", 13), fill=(70, 70, 95))

        if q3 is not None:
            draw.text((746, y + 8), _fmt_time(q3), font=_font("bold", 14), fill=(210, 130, 255))
        else:
            draw.text((746, y + 8), "—", font=_font("normal", 13), fill=(70, 70, 95))

        y += ROW_H

    # ── Footer ─────────────────────────────────────────────────────────
    draw.rectangle([0, H - FOOTER, W, H], fill=(11, 11, 18))
    draw.rectangle([0, H - FOOTER, W, H - FOOTER + 3], fill=(255, 200, 0))
    draw.text(
        (18, H - 34),
        "F1 Fantasy Manager  \u2022  Qualifying Complete  \u2022  /runrace to start",
        font=_font("normal", 13), fill=(90, 90, 120),
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()
