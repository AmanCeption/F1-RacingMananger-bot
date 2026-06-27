"""
Driver Detail Card Generator
Generates a driver profile card PNG — same style as qualifying_image.py.
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


# ── Stat bar colours ──────────────────────────────────────────────────────────
def _stat_color(val: int) -> tuple:
    if val >= 88:
        return (80, 220, 120)    # green  — elite
    if val >= 75:
        return (255, 210, 0)     # gold   — good
    if val >= 60:
        return (255, 140, 40)    # orange — average
    return (200, 60, 60)         # red    — weak


def _draw_stat_bar(
    draw: ImageDraw.ImageDraw,
    x: int, y: int,
    label: str, value: int,
    bar_w: int = 180, bar_h: int = 14,
) -> None:
    """Draw label + filled bar + numeric value on one line."""
    label_font  = _font("normal", 12)
    value_font  = _font("bold",   13)

    # Label
    draw.text((x, y), label, font=label_font, fill=(160, 160, 190))

    # Bar background
    bx = x + 130
    draw.rectangle([bx, y + 1, bx + bar_w, y + bar_h], fill=(30, 30, 48))

    # Filled portion
    fill_w = int(bar_w * value / 100)
    color  = _stat_color(value)
    if fill_w > 0:
        draw.rectangle([bx, y + 1, bx + fill_w, y + bar_h], fill=color)

    # Numeric value
    draw.text((bx + bar_w + 8, y), str(value), font=value_font, fill=color)


def generate_driver_card(
    name:                 str,
    nationality:          str,
    age:                  int,
    number:               int | None,
    is_fictional:         bool,
    skill:                int,
    racecraft:            int,
    pace:                 int,
    consistency:          int,
    wet_weather:          int,
    overtaking:           int,
    defence:              int,
    development_potential: int,
    base_salary:          int,
    is_free_agent:        bool,
    current_team:         str | None = None,
) -> bytes:
    """
    Generate driver profile card PNG.
    Returns PNG bytes.
    """
    W       = 680
    HERO_H  = 160
    STATS_H = 310   # 7 stats × 38px each + padding
    FOOTER  = 48
    H       = HERO_H + STATS_H + FOOTER

    img  = Image.new("RGB", (W, H), (11, 11, 18))
    draw = ImageDraw.Draw(img)

    overall = (skill + pace + racecraft) // 3

    # ── Hero Banner ───────────────────────────────────────────────────────────
    for i in range(HERO_H):
        shade = 20 + i // 5
        draw.line([(0, i), (W, i)], fill=(10, shade, shade + 10))

    draw.rectangle([0, 0, W, 6], fill=(255, 200, 0))
    draw.rectangle([0, HERO_H - 4, W, HERO_H], fill=(0, 140, 230))

    # Driver number badge
    num_str = f"#{number}" if number else "??"
    draw.ellipse([22, 22, 108, 108], fill=(0, 100, 180))
    draw.ellipse([26, 26, 104, 104], fill=(0, 130, 220))
    num_font = _font("bold", 28 if number and number >= 10 else 32)
    draw.text((40 if number and number >= 10 else 46, 48), num_str, font=num_font, fill=(255, 255, 255))

    # Name + meta
    draw.text((126, 18), "DRIVER PROFILE",     font=_font("bold",   12), fill=(0, 200, 255))
    draw.text((126, 38), name,                  font=_font("bold",   34), fill=(255, 255, 255))
    draw.text((128, 82), f"🌍 {nationality}  |  Age: {age}",
              font=_font("normal", 14), fill=(180, 180, 210))

    tag = "🤖 Fictional" if is_fictional else "🏎️ Real Driver"
    draw.text((128, 104), tag, font=_font("normal", 13), fill=(130, 130, 160))

    # Overall OVR badge — top right
    draw.rectangle([W - 110, 18, W - 18, 78], fill=(20, 20, 38))
    draw.rectangle([W - 110, 18, W - 18, 22], fill=_stat_color(overall))
    draw.text((W - 95, 26), "OVERALL",  font=_font("bold",   11), fill=(140, 140, 170))
    draw.text((W - 88, 40), str(overall), font=_font("bold",   28), fill=_stat_color(overall))

    # Status pill
    status_color = (40, 180, 80) if is_free_agent else (180, 60, 60)
    status_text  = "FREE AGENT" if is_free_agent else (current_team or "CONTRACTED")
    draw.rectangle([W - 160, 88, W - 18, 110], fill=status_color)
    draw.text((W - 153, 92), status_text[:18], font=_font("bold", 11), fill=(255, 255, 255))

    # ── Stats Section ─────────────────────────────────────────────────────────
    y = HERO_H + 16

    draw.text((18, y), "ATTRIBUTES", font=_font("bold", 13), fill=(100, 100, 140))
    draw.line([(18, y + 20), (W - 18, y + 20)], fill=(30, 30, 50), width=1)
    y += 30

    STATS = [
        ("Skill",           skill),
        ("Pace",            pace),
        ("Racecraft",       racecraft),
        ("Consistency",     consistency),
        ("Wet Weather",     wet_weather),
        ("Overtaking",      overtaking),
        ("Defence",         defence),
    ]

    for label, val in STATS:
        _draw_stat_bar(draw, 18, y, label, val)
        y += 34

    # ── Development + Salary row ──────────────────────────────────────────────
    y += 8
    draw.line([(18, y), (W - 18, y)], fill=(30, 30, 50), width=1)
    y += 10

    # Development potential bar (smaller, accent colour)
    draw.text((18, y), "Development Potential", font=_font("normal", 12), fill=(160, 160, 190))
    bx = 18 + 200
    bar_w = 160
    draw.rectangle([bx, y + 1, bx + bar_w, y + 14], fill=(30, 30, 48))
    fill_w = int(bar_w * development_potential / 100)
    dp_color = (180, 80, 255)  # purple for potential
    if fill_w > 0:
        draw.rectangle([bx, y + 1, bx + fill_w, y + 14], fill=dp_color)
    draw.text((bx + bar_w + 8, y), str(development_potential),
              font=_font("bold", 13), fill=dp_color)

    # Salary
    draw.text((W - 200, y), f"💰 ${base_salary:,}/yr",
              font=_font("bold", 14), fill=(255, 210, 0))

    # ── Footer ────────────────────────────────────────────────────────────────
    draw.rectangle([0, H - FOOTER, W, H], fill=(11, 11, 18))
    draw.rectangle([0, H - FOOTER, W, H - FOOTER + 3], fill=(0, 140, 230))
    draw.text(
        (18, H - 34),
        "F1 Fantasy Manager  •  Driver Stats  •  /market to sign",
        font=_font("normal", 13), fill=(90, 90, 120),
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()
