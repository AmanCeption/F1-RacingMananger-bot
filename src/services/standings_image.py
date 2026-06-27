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

    for idx, r in enumerate(results):
        pos        = r.get("position") or 0   # None -> 0 for DNF
        is_dnf     = r.get("dnf", False)
        row_color  = (22, 22, 38) if idx % 2 == 0 else (18, 18, 30)
        draw.rectangle([0, y - 4, W, y + ROW_H - 8], fill=row_color)

        # Left accent stripe for podium
        if pos in MEDALS:
            draw.rectangle([0, y - 4, 5, y + ROW_H - 8], fill=MEDALS[pos])

        pos_color = MEDALS.get(pos, (200, 200, 220))
        pos_display = str(pos) if pos > 0 else "DNF"
        draw.text((20, y + 10), pos_display, font=f_team, fill=pos_color)

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


def generate_constructor_championship_image(
    league_name: str,
    season: int,
    standings: list[dict],   # [{rank, team_name, points, wins, podiums, payout}]
    drivers: list[dict] = None,   # [{rank, driver_name, points}] optional
) -> bytes:
    """
    Generate a constructor championship table PNG for season-end screen.
    standings: list of dicts with rank, team_name, points, wins, podiums, payout
    drivers:   optional top-3 driver championship entries
    """
    ROW_H  = 58
    W      = 820
    HEADER = 90
    COL_H  = 30
    DRIVER_H = 0 if not drivers else (20 + 44 * min(3, len(drivers)))
    FOOTER = 52
    H = HEADER + COL_H + ROW_H * min(10, len(standings)) + DRIVER_H + FOOTER

    img  = Image.new("RGB", (W, H), color=(10, 10, 18))
    draw = ImageDraw.Draw(img)

    f_title  = _font("bold",   28)
    f_sub    = _font("normal", 15)
    f_team   = _font("bold",   17)
    f_small  = _font("normal", 13)
    f_med    = _font("bold",   14)

    # ── Header ─────────────────────────────────────────────────────────
    draw.rectangle([0, 0, W, HEADER - 2], fill=(18, 18, 32))
    draw.rectangle([0, HEADER - 5, W, HEADER], fill=(230, 0, 0))
    draw.text((20, 10), f"🏆  {league_name}", font=f_title, fill=(255, 215, 0))
    draw.text((22, 50), f"Season {season}  •  Constructor Championship Final Standings",
              font=f_sub, fill=(180, 180, 210))

    # ── Column headers ─────────────────────────────────────────────────
    y = HEADER + 4
    draw.text((20,  y), "POS",    font=f_small, fill=(100, 100, 140))
    draw.text((70,  y), "TEAM",   font=f_small, fill=(100, 100, 140))
    draw.text((440, y), "PTS",    font=f_small, fill=(100, 100, 140))
    draw.text((510, y), "WINS",   font=f_small, fill=(100, 100, 140))
    draw.text((580, y), "PODS",   font=f_small, fill=(100, 100, 140))
    draw.text((650, y), "PRIZE",  font=f_small, fill=(100, 100, 140))
    draw.rectangle([20, y + 20, W - 20, y + 21], fill=(35, 35, 55))
    y += COL_H

    MEDAL_COLORS = {1: (255, 215, 0), 2: (192, 192, 192), 3: (205, 127, 50)}
    ACCENT_COLORS = [
        (180, 0, 0), (0, 120, 215), (0, 160, 80),
        (160, 0, 160), (210, 100, 0), (0, 160, 160),
        (180, 60, 0), (80, 80, 180), (140, 0, 80), (60, 140, 0),
    ]

    for idx, row in enumerate(standings[:10]):
        rank       = row.get("rank", idx + 1)
        team_name  = row.get("team_name", "Unknown")[:32]
        pts        = row.get("points", 0)
        wins       = row.get("wins", 0)
        podiums    = row.get("podiums", 0)
        payout     = row.get("payout", 0)

        row_fill = (20, 20, 36) if idx % 2 == 0 else (14, 14, 26)
        draw.rectangle([0, y - 4, W, y + ROW_H - 8], fill=row_fill)

        # Left accent stripe — team colour
        accent = MEDAL_COLORS.get(rank, ACCENT_COLORS[idx % len(ACCENT_COLORS)])
        draw.rectangle([0, y - 4, 5, y + ROW_H - 8], fill=accent)

        # Rank
        rank_color = MEDAL_COLORS.get(rank, (200, 200, 220))
        draw.text((20, y + 12), str(rank), font=f_team, fill=rank_color)

        # Team name — champion gets star
        name_label = f"👑 {team_name}" if rank == 1 else team_name
        draw.text((70, y + 12), name_label, font=f_team, fill=(230, 230, 255))

        # Stats
        pts_color = MEDAL_COLORS.get(rank, (200, 210, 255))
        draw.text((440, y + 12), str(pts),    font=f_team, fill=pts_color)
        draw.text((510, y + 12), str(wins),   font=f_med,  fill=(255, 190, 0) if wins > 0 else (120, 120, 150))
        draw.text((580, y + 12), str(podiums),font=f_med,  fill=(180, 180, 200))
        payout_str = f"${payout // 1_000_000}M" if payout >= 1_000_000 else f"${payout:,}"
        draw.text((650, y + 12), payout_str,  font=f_med,  fill=(80, 220, 120))

        y += ROW_H

    # ── Driver Championship Mini-Table ──────────────────────────────────
    if drivers:
        y += 8
        draw.rectangle([20, y, W - 20, y + 1], fill=(40, 40, 65))
        y += 8
        draw.text((20, y), "🏎️  Drivers Championship", font=f_med, fill=(180, 180, 220))
        y += 22
        for dr in drivers[:3]:
            rank = dr.get("rank", 0)
            name = dr.get("driver_name", "")[:30]
            pts  = dr.get("points", 0)
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"P{rank}")
            draw.text((20, y), f"{medal}  {name}", font=f_team, fill=(230, 230, 255))
            draw.text((500, y), f"{pts} pts", font=f_team,
                      fill=MEDAL_COLORS.get(rank, (200, 200, 230)))
            y += 44

    # ── Footer ─────────────────────────────────────────────────────────
    draw.rectangle([0, H - FOOTER, W, H], fill=(10, 10, 18))
    draw.rectangle([0, H - FOOTER, W, H - FOOTER + 3], fill=(230, 0, 0))
    draw.text((20, H - 34), f"F1 Fantasy Manager  •  Season {season} Complete",
              font=f_small, fill=(80, 80, 110))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()
