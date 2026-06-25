"""
Configuration - pydantic-free version for Render compatibility
"""
import os
from dotenv import load_dotenv

load_dotenv()

def _parse_admin_ids(raw: str) -> list[int]:
    raw = raw.strip().strip("[]")
    if not raw:
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: list[int] = _parse_admin_ids(os.getenv("ADMIN_IDS", "[]"))

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://f1bot:f1bot@localhost:5432/f1bot"
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Game Settings
    STARTING_BUDGET: int = int(os.getenv("STARTING_BUDGET", "100000000"))
    MAX_TEAMS_PER_LEAGUE: int = int(os.getenv("MAX_TEAMS_PER_LEAGUE", "20"))
    SEASON_RACES: int = int(os.getenv("SEASON_RACES", "24"))
    WEEKLY_RESEARCH_POINTS: int = int(os.getenv("WEEKLY_RESEARCH_POINTS", "50"))
    DAILY_REWARD_MONEY: int = int(os.getenv("DAILY_REWARD_MONEY", "500000"))
    DAILY_REWARD_RP: int = int(os.getenv("DAILY_REWARD_RP", "10"))

    RACE_HOUR: int = int(os.getenv("RACE_HOUR", "14"))
    RACE_MINUTE: int = int(os.getenv("RACE_MINUTE", "0"))

    COMMAND_COOLDOWN: int = int(os.getenv("COMMAND_COOLDOWN", "3"))
    MAX_COMMANDS_PER_MINUTE: int = int(os.getenv("MAX_COMMANDS_PER_MINUTE", "20"))

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/bot.log")


settings = Settings()

# F1 Points System
F1_POINTS = {
    1: 25, 2: 18, 3: 15, 4: 12, 5: 10,
    6: 8, 7: 6, 8: 4, 9: 2, 10: 1
}

# F1 Calendar
# Sprint rounds — real 2024 schedule (round indices, 0-based)
SPRINT_ROUNDS = {4, 10, 13, 18, 20, 23}   # China, Austria, Belgium, USA, Brazil, Qatar

# Circuit DNA traits applied during race simulation
# overtaking_mod: >1 = more overtakes, <1 = less
# engine_mod: power-sensitive circuits boost engine stat
# weather_volatile: true = higher chance of rain/mixed
# tyre_stress: higher = tyres degrade faster
CIRCUIT_DNA = {
    "Bahrain Grand Prix":        {"overtaking_mod": 1.1,  "engine_mod": 1.0,  "weather_volatile": False, "tyre_stress": 1.1},
    "Saudi Arabian Grand Prix":  {"overtaking_mod": 1.15, "engine_mod": 1.15, "weather_volatile": False, "tyre_stress": 0.9},
    "Australian Grand Prix":     {"overtaking_mod": 1.0,  "engine_mod": 1.0,  "weather_volatile": True,  "tyre_stress": 1.0},
    "Japanese Grand Prix":       {"overtaking_mod": 0.9,  "engine_mod": 1.05, "weather_volatile": True,  "tyre_stress": 1.2},
    "Chinese Grand Prix":        {"overtaking_mod": 1.1,  "engine_mod": 1.0,  "weather_volatile": False, "tyre_stress": 1.0},
    "Miami Grand Prix":          {"overtaking_mod": 1.05, "engine_mod": 1.0,  "weather_volatile": False, "tyre_stress": 1.1},
    "Emilia Romagna Grand Prix": {"overtaking_mod": 0.85, "engine_mod": 1.05, "weather_volatile": True,  "tyre_stress": 1.0},
    "Monaco Grand Prix":         {"overtaking_mod": 0.25, "engine_mod": 0.7,  "weather_volatile": False, "tyre_stress": 0.8,  "note": "Impossible to overtake. Quali everything."},
    "Canadian Grand Prix":       {"overtaking_mod": 1.2,  "engine_mod": 1.1,  "weather_volatile": True,  "tyre_stress": 0.9},
    "Spanish Grand Prix":        {"overtaking_mod": 0.85, "engine_mod": 1.0,  "weather_volatile": False, "tyre_stress": 1.15},
    "Austrian Grand Prix":       {"overtaking_mod": 1.2,  "engine_mod": 0.95, "weather_volatile": True,  "tyre_stress": 1.0},
    "British Grand Prix":        {"overtaking_mod": 1.0,  "engine_mod": 1.0,  "weather_volatile": True,  "tyre_stress": 1.1},
    "Hungarian Grand Prix":      {"overtaking_mod": 0.7,  "engine_mod": 0.8,  "weather_volatile": False, "tyre_stress": 1.1,  "note": "Monaco-lite. Aero & chassis king."},
    "Belgian Grand Prix":        {"overtaking_mod": 1.1,  "engine_mod": 1.2,  "weather_volatile": True,  "tyre_stress": 1.0,  "note": "Spa — weather-volatile, engine power critical."},
    "Dutch Grand Prix":          {"overtaking_mod": 0.75, "engine_mod": 0.9,  "weather_volatile": True,  "tyre_stress": 1.1},
    "Italian Grand Prix":        {"overtaking_mod": 1.3,  "engine_mod": 1.35, "weather_volatile": False, "tyre_stress": 0.8,  "note": "Monza — pure power. Low drag essential."},
    "Azerbaijan Grand Prix":     {"overtaking_mod": 1.25, "engine_mod": 1.2,  "weather_volatile": False, "tyre_stress": 0.85},
    "Singapore Grand Prix":      {"overtaking_mod": 0.6,  "engine_mod": 0.75, "weather_volatile": True,  "tyre_stress": 1.2,  "note": "Street circuit. Aero & chassis dominant."},
    "United States Grand Prix":  {"overtaking_mod": 1.1,  "engine_mod": 1.0,  "weather_volatile": False, "tyre_stress": 1.1},
    "Mexico City Grand Prix":    {"overtaking_mod": 1.0,  "engine_mod": 1.3,  "weather_volatile": False, "tyre_stress": 0.9,  "note": "High altitude — engine power amplified."},
    "São Paulo Grand Prix":      {"overtaking_mod": 1.15, "engine_mod": 1.1,  "weather_volatile": True,  "tyre_stress": 1.0},
    "Las Vegas Grand Prix":      {"overtaking_mod": 1.2,  "engine_mod": 1.2,  "weather_volatile": False, "tyre_stress": 0.85},
    "Qatar Grand Prix":          {"overtaking_mod": 0.9,  "engine_mod": 1.0,  "weather_volatile": False, "tyre_stress": 1.3},
    "Abu Dhabi Grand Prix":      {"overtaking_mod": 0.95, "engine_mod": 1.0,  "weather_volatile": False, "tyre_stress": 1.0},
}

F1_CALENDAR = [
    {"name": "Bahrain Grand Prix",        "circuit": "Bahrain International Circuit",    "laps": 57, "country": "🇧🇭"},
    {"name": "Saudi Arabian Grand Prix",  "circuit": "Jeddah Corniche Circuit",          "laps": 50, "country": "🇸🇦"},
    {"name": "Australian Grand Prix",     "circuit": "Albert Park Circuit",              "laps": 58, "country": "🇦🇺"},
    {"name": "Japanese Grand Prix",       "circuit": "Suzuka International Racing Course","laps": 53, "country": "🇯🇵"},
    {"name": "Chinese Grand Prix",        "circuit": "Shanghai International Circuit",   "laps": 56, "country": "🇨🇳",  "sprint": True},
    {"name": "Miami Grand Prix",          "circuit": "Miami International Autodrome",    "laps": 57, "country": "🇺🇸"},
    {"name": "Emilia Romagna Grand Prix", "circuit": "Autodromo Enzo e Dino Ferrari",    "laps": 63, "country": "🇮🇹"},
    {"name": "Monaco Grand Prix",         "circuit": "Circuit de Monaco",                "laps": 78, "country": "🇲🇨"},
    {"name": "Canadian Grand Prix",       "circuit": "Circuit Gilles Villeneuve",        "laps": 70, "country": "🇨🇦"},
    {"name": "Spanish Grand Prix",        "circuit": "Circuit de Barcelona-Catalunya",   "laps": 66, "country": "🇪🇸"},
    {"name": "Austrian Grand Prix",       "circuit": "Red Bull Ring",                    "laps": 71, "country": "🇦🇹",  "sprint": True},
    {"name": "British Grand Prix",        "circuit": "Silverstone Circuit",              "laps": 52, "country": "🇬🇧"},
    {"name": "Hungarian Grand Prix",      "circuit": "Hungaroring",                      "laps": 70, "country": "🇭🇺"},
    {"name": "Belgian Grand Prix",        "circuit": "Circuit de Spa-Francorchamps",     "laps": 44, "country": "🇧🇪",  "sprint": True},
    {"name": "Dutch Grand Prix",          "circuit": "Circuit Zandvoort",                "laps": 72, "country": "🇳🇱"},
    {"name": "Italian Grand Prix",        "circuit": "Autodromo Nazionale Monza",        "laps": 53, "country": "🇮🇹"},
    {"name": "Azerbaijan Grand Prix",     "circuit": "Baku City Circuit",                "laps": 51, "country": "🇦🇿"},
    {"name": "Singapore Grand Prix",      "circuit": "Marina Bay Street Circuit",        "laps": 62, "country": "🇸🇬"},
    {"name": "United States Grand Prix",  "circuit": "Circuit of the Americas",          "laps": 56, "country": "🇺🇸",  "sprint": True},
    {"name": "Mexico City Grand Prix",    "circuit": "Autodromo Hermanos Rodriguez",     "laps": 71, "country": "🇲🇽"},
    {"name": "São Paulo Grand Prix",      "circuit": "Autodromo Jose Carlos Pace",       "laps": 71, "country": "🇧🇷",  "sprint": True},
    {"name": "Las Vegas Grand Prix",      "circuit": "Las Vegas Strip Circuit",          "laps": 50, "country": "🇺🇸"},
    {"name": "Qatar Grand Prix",          "circuit": "Lusail International Circuit",     "laps": 57, "country": "🇶🇦",  "sprint": True},
    {"name": "Abu Dhabi Grand Prix",      "circuit": "Yas Marina Circuit",               "laps": 58, "country": "🇦🇪"},
]

TYRE_DATA = {
    "soft":  {"pace": 1.0, "wear_rate": 0.035, "color": "🔴"},
    "medium": {"pace": 0.97, "wear_rate": 0.022, "color": "🟡"},
    "hard":  {"pace": 0.94, "wear_rate": 0.014, "color": "⚪"},
    "intermediate": {"pace": 0.90, "wear_rate": 0.025, "color": "🟢"},
    "wet":   {"pace": 0.85, "wear_rate": 0.030, "color": "🔵"},
}
