"""
Circuit Images Service
Fetches F1 circuit track map images from Wikimedia Commons.
Falls back to a generic F1 logo URL if not found.
"""
import logging
import aiohttp

logger = logging.getLogger(__name__)

# Fallback image if fetch fails
FALLBACK_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/thumb/3/33/F1_logo.svg/320px-F1_logo.svg.png"

# Wikimedia Commons filenames for each circuit track map
CIRCUIT_IMAGES: dict[str, str] = {
    # Grand Prix Name → Wikimedia Commons file title
    "Bahrain Grand Prix":           "Bahrain_International_Circuit_layout.svg",
    "Saudi Arabian Grand Prix":     "Jeddah_Corniche_Circuit_2021.svg",
    "Australian Grand Prix":        "Albert_Park_Circuit_2021.svg",
    "Japanese Grand Prix":          "Suzuka_circuit_map.svg",
    "Chinese Grand Prix":           "Shanghai_International_Circuit.svg",
    "Miami Grand Prix":             "Miami_International_Autodrome_track_map.svg",
    "Emilia Romagna Grand Prix":    "Autodromo_Enzo_e_Dino_Ferrari_track_map.svg",
    "Monaco Grand Prix":            "Circuit_de_Monaco.svg",
    "Canadian Grand Prix":          "Circuit_Gilles_Villeneuve_track_map.svg",
    "Spanish Grand Prix":           "Circuit_de_Barcelona-Catalunya_track_map.svg",
    "Austrian Grand Prix":          "Red_Bull_Ring_track_map.svg",
    "British Grand Prix":           "Silverstone_circuit_2020.svg",
    "Hungarian Grand Prix":         "Hungaroring_track_map.svg",
    "Belgian Grand Prix":           "Spa-Francorchamps_track_map.svg",
    "Dutch Grand Prix":             "Zandvoort_track_map.svg",
    "Italian Grand Prix":           "Autodromo_Nazionale_Monza_track_map.svg",
    "Azerbaijan Grand Prix":        "Baku_City_Circuit_track_map.svg",
    "Singapore Grand Prix":         "Marina_Bay_Street_Circuit_track_map.svg",
    "United States Grand Prix":     "Circuit_of_the_Americas_track_map.svg",
    "Mexico City Grand Prix":       "Autodromo_Hermanos_Rodriguez_track_map.svg",
    "São Paulo Grand Prix":         "Autodromo_Jose_Carlos_Pace_track_map.svg",
    "Las Vegas Grand Prix":         "Las_Vegas_Strip_Circuit_track_map.svg",
    "Qatar Grand Prix":             "Lusail_International_Circuit_track_map.svg",
    "Abu Dhabi Grand Prix":         "Yas_Marina_Circuit_track_map.svg",
}

WIKIMEDIA_API = "https://en.wikipedia.org/w/api.php"


async def get_circuit_image_url(race_name: str) -> str:
    """
    Returns a direct image URL for the given race/GP name.
    Uses Wikimedia API to resolve the file to a direct URL.
    Falls back to FALLBACK_IMAGE on any error.
    """
    filename = CIRCUIT_IMAGES.get(race_name)
    if not filename:
        logger.warning(f"No circuit image mapping for: {race_name}")
        return FALLBACK_IMAGE

    try:
        params = {
            "action": "query",
            "titles": f"File:{filename}",
            "prop": "imageinfo",
            "iiprop": "url",
            "format": "json",
        }
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            async with session.get(WIKIMEDIA_API, params=params) as resp:
                if resp.status != 200:
                    return FALLBACK_IMAGE
                data = await resp.json()
                pages = data.get("query", {}).get("pages", {})
                for page in pages.values():
                    imageinfo = page.get("imageinfo", [])
                    if imageinfo:
                        url = imageinfo[0].get("url", "")
                        if url:
                            logger.info(f"Circuit image resolved: {url}")
                            return url
    except Exception as e:
        logger.warning(f"Circuit image fetch failed for {race_name}: {e}")

    return FALLBACK_IMAGE
