"""
Standings Image Generator
Generates a race result card image using Pillow.
Returns bytes (PNG) ready to send via bot.send_photo().
"""
import io
import logging
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Font paths (DejaVu ships with most Linux/Render environments)
_FONT_PATHS = {
    "bold":   "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "normal": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
}


def _font(style: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(_FONT_PATHS[style], size)
    except Exception:
        return ImageFont.load_default()


def generate_race_standings_image(
    race_name: str,
    circuit: str,
    weather_label: str,
    results: list[dict],
) -> bytes:
    """
    Generate a race result card PNG.

    results: list of dicts with keys:
        position (int), team (str), driver (str),
        points (int), total_points (int),
        dnf (bool), fastest_lap (bool)

    Returns PNG bytes.
    """
    ROW_H   = 54
    W       = 800
    HEADER  = 80
    COL_H   = 28
    FOOTER  = 52
    H = HEADER + COL_H + ROW_H * len(results) + FOOTER

    img  = Image.new("RGB", (W, H), color=(13, 13, 20))
    draw = ImageDraw.Draw(img)

    # ── Fonts ──────────────────────────────────────────────────────────
    f_title = _font("bold",   26)
    f_sub   = _font("normal", 15)
    f_team  = _font("bold",   16)
    f_small = _font("normal", 13)

    # ── Header ─────────────────────────────────────────────────────────
    draw.rectangle([0, 0, W, HEADER - 2], fill=(20, 20, 35))
    draw.rectangle([0, HEADER - 4, W, HEADER], fill=(230, 0, 0))

    draw.text((20, 12), f"\U0001f3c1  {race_name}", font=f_title, fill=(255, 255, 255))
    draw.text((22, 48), f"{circuit}    {weather_label}",  font=f_sub,   fill=(180, 180, 200))

    # ── Column headers ─────────────────────────────────────────────────
    y = HEADER + 4
    draw.text((20,  y), "POS",    font=f_small, fill=(120, 120, 150))
    draw.text((65,  y), "TEAM",   font=f_small, fill=(120, 120, 150))
    draw.text((430, y), "DRIVER", font=f_small, fill=(120, 120, 150))
    draw.text((600, y), "+PTS",   font=f_small, fill=(120, 120, 150))
    draw.text((680, y), "TOTAL",  font=f_small, fill=(120, 120, 150))
    draw.rectangle([20, y + 18, W - 20, y + 19], fill=(40, 40, 60))

    y += COL_H
    MEDALS = {1: (255, 215, 0), 2: (192, 192, 192), 3: (205, 127, 50)}

    for r in results:
        pos        = r.get("position", 0)
        is_dnf     = r.get("dnf", False)
        row_color  = (22, 22, 38) if pos % 2 == 0 else (18, 18, 30)
        draw.rectangle([0, y - 4, W, y + ROW_H - 8], fill=row_color)

        # Left accent stripe for podium
        if pos in MEDALS:
            draw.rectangle([0, y - 4, 5, y + ROW_H - 8], fill=MEDALS[pos])

        pos_color = MEDALS.get(pos, (200, 200, 220))
        draw.text((20, y + 10), str(pos), font=f_team, fill=pos_color)

        team_str = r.get("team", "")[:30]
        driver_str = r.get("driver", "")

        if is_dnf:
            # DNF badge
            draw.rectangle([58, y + 8, 112, y + 30], fill=(100, 0, 0))
            draw.text((63, y + 9), "DNF", font=f_small, fill=(255, 80, 80))
            draw.text((120, y + 10), team_str, font=f_team, fill=(160, 100, 100))
        else:
            draw.text((65, y + 10), team_str, font=f_team, fill=(230, 230, 255))

        draw.text((430, y + 10), driver_str, font=f_small, fill=(170, 170, 195))

        pts_str   = f"+{r.get('points', 0)}" if not is_dnf else "\u2014"
        pts_color = (100, 220, 100) if not is_dnf else (150, 50, 50)
        draw.text((600, y + 10), pts_str, font=f_team, fill=pts_color)

        total_color = (255, 215, 0) if pos == 1 else (210, 210, 230)
        draw.text((680, y + 10), str(r.get("total_points", 0)), font=f_team, fill=total_color)

        if r.get("fastest_lap"):
            draw.text((762, y + 10), "\u26a1", font=f_small, fill=(160, 100, 255))

        y += ROW_H

    # ── Footer ─────────────────────────────────────────────────────────
    draw.rectangle([0, H - FOOTER, W, H], fill=(13, 13, 20))
    draw.rectangle([0, H - FOOTER, W, H - FOOTER + 3], fill=(230, 0, 0))
    draw.text((20, H - 34), "F1 Fantasy Manager  \u2022  /standings for full season table",
              font=f_small, fill=(90, 90, 120))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()
