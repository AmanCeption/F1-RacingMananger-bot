"""
Circuit Images Service
Generates a styled circuit info card using Pillow (no external API needed).
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


# Circuit data: name → (laps, country_flag, track_length_km, lap_record, record_holder, first_gp)
CIRCUIT_DATA: dict[str, dict] = {
    "Bahrain Grand Prix":        {"circuit":"Bahrain International Circuit","laps":57,"flag":"🇧🇭","length":"5.412","record":"1:31.447","holder":"P. de la Rosa (2005)","first_gp":2004,"turns":15,"drs":3},
    "Saudi Arabian Grand Prix":  {"circuit":"Jeddah Corniche Circuit","laps":50,"flag":"🇸🇦","length":"6.174","record":"1:30.734","holder":"L. Hamilton (2021)","first_gp":2021,"turns":27,"drs":3},
    "Australian Grand Prix":     {"circuit":"Albert Park Circuit","laps":58,"flag":"🇦🇺","length":"5.278","record":"1:20.235","holder":"C. Leclerc (2022)","first_gp":1996,"turns":16,"drs":4},
    "Japanese Grand Prix":       {"circuit":"Suzuka International Racing Course","laps":53,"flag":"🇯🇵","length":"5.807","record":"1:30.983","holder":"K. Räikkönen (2005)","first_gp":1987,"turns":18,"drs":2},
    "Chinese Grand Prix":        {"circuit":"Shanghai International Circuit","laps":56,"flag":"🇨🇳","length":"5.451","record":"1:32.238","holder":"M. Schumacher (2004)","first_gp":2004,"turns":16,"drs":2},
    "Miami Grand Prix":          {"circuit":"Miami International Autodrome","laps":57,"flag":"🇺🇸","length":"5.412","record":"1:29.708","holder":"M. Verstappen (2023)","first_gp":2022,"turns":19,"drs":3},
    "Emilia Romagna Grand Prix": {"circuit":"Autodromo Enzo e Dino Ferrari","laps":63,"flag":"🇮🇹","length":"4.909","record":"1:15.484","holder":"M. Verstappen (2022)","first_gp":1980,"turns":17,"drs":2},
    "Monaco Grand Prix":         {"circuit":"Circuit de Monaco","laps":78,"flag":"🇲🇨","length":"3.337","record":"1:12.909","holder":"L. Hamilton (2021)","first_gp":1950,"turns":19,"drs":1},
    "Canadian Grand Prix":       {"circuit":"Circuit Gilles Villeneuve","laps":70,"flag":"🇨🇦","length":"4.361","record":"1:13.078","holder":"V. Bottas (2019)","first_gp":1978,"turns":14,"drs":3},
    "Spanish Grand Prix":        {"circuit":"Circuit de Barcelona-Catalunya","laps":66,"flag":"🇪🇸","length":"4.657","record":"1:18.149","holder":"M. Verstappen (2021)","first_gp":1991,"turns":16,"drs":2},
    "Austrian Grand Prix":       {"circuit":"Red Bull Ring","laps":71,"flag":"🇦🇹","length":"4.318","record":"1:05.619","holder":"C. Leclerc (2020)","first_gp":1970,"turns":10,"drs":3},
    "British Grand Prix":        {"circuit":"Silverstone Circuit","laps":52,"flag":"🇬🇧","length":"5.891","record":"1:27.097","holder":"M. Verstappen (2020)","first_gp":1950,"turns":18,"drs":2},
    "Hungarian Grand Prix":      {"circuit":"Hungaroring","laps":70,"flag":"🇭🇺","length":"4.381","record":"1:16.627","holder":"L. Hamilton (2020)","first_gp":1986,"turns":14,"drs":1},
    "Belgian Grand Prix":        {"circuit":"Circuit de Spa-Francorchamps","laps":44,"flag":"🇧🇪","length":"7.004","record":"1:46.286","holder":"V. Bottas (2018)","first_gp":1950,"turns":19,"drs":3},
    "Dutch Grand Prix":          {"circuit":"Circuit Zandvoort","laps":72,"flag":"🇳🇱","length":"4.259","record":"1:11.097","holder":"M. Verstappen (2021)","first_gp":1952,"turns":14,"drs":2},
    "Italian Grand Prix":        {"circuit":"Autodromo Nazionale Monza","laps":53,"flag":"🇮🇹","length":"5.793","record":"1:21.046","holder":"R. Barrichello (2004)","first_gp":1950,"turns":11,"drs":3},
    "Azerbaijan Grand Prix":     {"circuit":"Baku City Circuit","laps":51,"flag":"🇦🇿","length":"6.003","record":"1:43.009","holder":"C. Leclerc (2019)","first_gp":2016,"turns":20,"drs":2},
    "Singapore Grand Prix":      {"circuit":"Marina Bay Street Circuit","laps":62,"flag":"🇸🇬","length":"4.940","record":"1:35.867","holder":"K. Räikkönen (2018)","first_gp":2008,"turns":23,"drs":3},
    "United States Grand Prix":  {"circuit":"Circuit of the Americas","laps":56,"flag":"🇺🇸","length":"5.513","record":"1:36.169","holder":"C. Leclerc (2019)","first_gp":2012,"turns":20,"drs":2},
    "Mexico City Grand Prix":    {"circuit":"Autodromo Hermanos Rodriguez","laps":71,"flag":"🇲🇽","length":"4.304","record":"1:17.774","holder":"V. Bottas (2021)","first_gp":1963,"turns":17,"drs":3},
    "São Paulo Grand Prix":      {"circuit":"Autodromo Jose Carlos Pace","laps":71,"flag":"🇧🇷","length":"4.309","record":"1:10.540","holder":"V. Bottas (2018)","first_gp":1973,"turns":15,"drs":2},
    "Las Vegas Grand Prix":      {"circuit":"Las Vegas Strip Circuit","laps":50,"flag":"🇺🇸","length":"6.201","record":"1:35.490","holder":"O. Piastri (2024)","first_gp":2023,"turns":17,"drs":3},
    "Qatar Grand Prix":          {"circuit":"Lusail International Circuit","laps":57,"flag":"🇶🇦","length":"5.380","record":"1:24.319","holder":"M. Verstappen (2023)","first_gp":2021,"turns":16,"drs":2},
    "Abu Dhabi Grand Prix":      {"circuit":"Yas Marina Circuit","laps":58,"flag":"🇦🇪","length":"5.281","record":"1:26.103","holder":"M. Verstappen (2021)","first_gp":2009,"turns":16,"drs":2},
}


def generate_circuit_card(race_name: str, round_num: int = 0, weather: str = "") -> bytes:
    """
    Generate a styled circuit info card PNG using Pillow.
    Returns PNG bytes.
    """
    data = CIRCUIT_DATA.get(race_name, {})
    circuit_name = data.get("circuit", race_name)
    flag         = data.get("flag", "🏁")
    laps         = data.get("laps", "—")
    length       = data.get("length", "—")
    record       = data.get("record", "—")
    holder       = data.get("holder", "—")
    first_gp     = data.get("first_gp", "—")
    turns        = data.get("turns", "—")
    drs          = data.get("drs", "—")

    W, H = 800, 340
    BG   = (10, 10, 20)
    RED  = (220, 0, 0)
    GOLD = (255, 200, 0)
    WHITE = (240, 240, 255)
    DIM  = (130, 130, 160)
    CARD = (18, 18, 36)

    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Background gradient-like strips
    for i in range(H):
        shade = max(0, 10 + i // 20)
        draw.line([(0, i), (W, i)], fill=(shade, shade, shade + 8))

    # Top red bar
    draw.rectangle([0, 0, W, 7], fill=RED)

    # Header block
    draw.rectangle([0, 7, W, 90], fill=(16, 16, 32))
    round_text = f"ROUND {round_num}  •  " if round_num else ""
    draw.text((20, 14), f"{round_text}FORMULA 1 GRAND PRIX", font=_font("normal", 13), fill=RED)
    draw.text((20, 34), race_name.upper(), font=_font("bold", 26), fill=WHITE)
    draw.text((20, 68), circuit_name, font=_font("normal", 15), fill=DIM)

    # Flag big on right
    try:
        draw.text((W - 80, 20), flag, font=_font("normal", 52), fill=WHITE)
    except Exception:
        pass

    # Red separator
    draw.rectangle([0, 90, W, 94], fill=RED)

    # Stats grid — 3 columns x 2 rows
    stats = [
        ("🔢 LAPS",       str(laps)),
        ("📏 LENGTH",     f"{length} km"),
        ("↩️ TURNS",      str(turns)),
        ("⚡ DRS ZONES",  str(drs)),
        ("🏆 LAP RECORD", record),
        ("👤 HELD BY",    holder),
    ]

    COL_W = W // 3
    ROW_H = 70
    y_start = 104

    for i, (label, value) in enumerate(stats):
        col = i % 3
        row = i // 3
        x = col * COL_W + 20
        y = y_start + row * ROW_H

        # Card background
        draw.rectangle([col * COL_W + 6, y - 8, (col + 1) * COL_W - 6, y + ROW_H - 12], fill=CARD)

        draw.text((x, y),      label, font=_font("normal", 11), fill=DIM)
        # Truncate long values
        val_display = value if len(value) <= 22 else value[:20] + "…"
        draw.text((x, y + 16), val_display, font=_font("bold", 17), fill=WHITE)

    # Bottom bar
    bottom_y = y_start + 2 * ROW_H + 10
    draw.rectangle([0, bottom_y, W, H], fill=(12, 12, 24))
    draw.rectangle([0, bottom_y, W, bottom_y + 3], fill=GOLD)

    footer_parts = [f"First GP: {first_gp}"]
    if weather:
        footer_parts.append(f"Weather: {weather.replace('_', ' ').title()}")
    footer_parts.append("F1 Fantasy Manager")

    draw.text((20, bottom_y + 12), "  •  ".join(footer_parts),
              font=_font("normal", 13), fill=(140, 140, 170))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()


# Keep old function signature for backward compat (returns bytes now, not URL)
async def get_circuit_image_url(race_name: str) -> str:
    """Legacy — kept for compat. Use generate_circuit_card() instead."""
    return ""
