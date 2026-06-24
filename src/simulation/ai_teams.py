"""
AI Teams Database
Realistic AI-controlled teams with distinct personalities, strengths, and weaknesses.
Used to fill leagues when there aren't enough human players.
"""
import random

# ─────────────────────────────────────────────────────────────────────────────
# AI TEAM ARCHETYPES
# Each team has:
#   personality  → affects strategy choices + in-race behavior
#   tier         → 1=dominant, 2=midfield, 3=backmarker (affects base stats)
#   strengths    → which car stats are boosted
#   weakness     → which car stat is penalised
# ─────────────────────────────────────────────────────────────────────────────

AI_TEAMS = [
    # ── TIER 1 — Dominant / Championship contenders ───────────────────────
    {
        "name": "Apex Motorsport",
        "personality": "aggressive",
        "tier": 1,
        "lore": "A budget-unlimited powerhouse known for bold undercut strategies.",
        "strengths": ["engine", "aerodynamics"],
        "weakness": "reliability",
        "driver": {"name": "Viktor Bauer", "nationality": "German",
                   "pace": 95, "racecraft": 94, "consistency": 88,
                   "wet_weather": 90, "overtaking": 93, "defence": 89},
        "driver2": {"name": "Ren Nakashima", "nationality": "Japanese",
                    "pace": 91, "racecraft": 90, "consistency": 92,
                    "wet_weather": 88, "overtaking": 86, "defence": 91},
    },
    {
        "name": "Velocity Racing",
        "personality": "calculated",
        "tier": 1,
        "lore": "Data-driven team that maximises tyre life and nails strategy calls.",
        "strengths": ["aerodynamics", "chassis"],
        "weakness": "pit_crew",
        "driver": {"name": "Ethan Mercier", "nationality": "French",
                   "pace": 93, "racecraft": 92, "consistency": 95,
                   "wet_weather": 87, "overtaking": 88, "defence": 93},
        "driver2": {"name": "Layla Osei", "nationality": "Ghanaian",
                    "pace": 89, "racecraft": 91, "consistency": 90,
                    "wet_weather": 85, "overtaking": 84, "defence": 88},
    },

    # ── TIER 2 — Midfield / Occasional podium hunters ─────────────────────
    {
        "name": "Iron Peak Racing",
        "personality": "consistent",
        "tier": 2,
        "lore": "Reliable points scorers — never spectacular but never embarrassing.",
        "strengths": ["chassis", "reliability"],
        "weakness": "engine",
        "driver": {"name": "Marco Ferrini", "nationality": "Italian",
                   "pace": 84, "racecraft": 85, "consistency": 91,
                   "wet_weather": 82, "overtaking": 80, "defence": 87},
        "driver2": {"name": "Sven Holmqvist", "nationality": "Swedish",
                    "pace": 82, "racecraft": 83, "consistency": 89,
                    "wet_weather": 84, "overtaking": 78, "defence": 85},
    },
    {
        "name": "Storm Works F1",
        "personality": "wet_specialist",
        "tier": 2,
        "lore": "Underrated in dry conditions but absolutely lethal in the rain.",
        "strengths": ["chassis", "tyre_mgmt"],
        "weakness": "aerodynamics",
        "driver": {"name": "Cillian Byrne", "nationality": "Irish",
                   "pace": 83, "racecraft": 86, "consistency": 82,
                   "wet_weather": 96, "overtaking": 85, "defence": 83},
        "driver2": {"name": "Pita Ravouvou", "nationality": "Fijian",
                    "pace": 80, "racecraft": 82, "consistency": 80,
                    "wet_weather": 93, "overtaking": 79, "defence": 80},
    },
    {
        "name": "Centauri Grand Prix",
        "personality": "opportunist",
        "tier": 2,
        "lore": "Known for gambles — safety car calls, early pits, and risky overtakes.",
        "strengths": ["pit_crew", "aerodynamics"],
        "weakness": "consistency",
        "driver": {"name": "Diego Reyes", "nationality": "Mexican",
                   "pace": 85, "racecraft": 88, "consistency": 75,
                   "wet_weather": 83, "overtaking": 92, "defence": 79},
        "driver2": {"name": "Anya Petrov", "nationality": "Russian",
                    "pace": 82, "racecraft": 84, "consistency": 73,
                    "wet_weather": 81, "overtaking": 88, "defence": 76},
    },
    {
        "name": "Meridian Motorsport",
        "personality": "defensive",
        "tier": 2,
        "lore": "Masters of holding position — notoriously hard to overtake.",
        "strengths": ["chassis", "pit_crew"],
        "weakness": "overtaking",
        "driver": {"name": "Tobias Weller", "nationality": "Austrian",
                   "pace": 81, "racecraft": 83, "consistency": 86,
                   "wet_weather": 80, "overtaking": 72, "defence": 94},
        "driver2": {"name": "Song Wei", "nationality": "Chinese",
                    "pace": 79, "racecraft": 81, "consistency": 85,
                    "wet_weather": 78, "overtaking": 70, "defence": 92},
    },

    # ── TIER 3 — Backmarkers / Character teams ────────────────────────────
    {
        "name": "Sandstorm Racing",
        "personality": "erratic",
        "tier": 3,
        "lore": "Genuinely unpredictable — P8 one race, DNF the next.",
        "strengths": ["engine"],
        "weakness": "reliability",
        "driver": {"name": "Farrukh Tashkentov", "nationality": "Uzbek",
                   "pace": 74, "racecraft": 73, "consistency": 62,
                   "wet_weather": 70, "overtaking": 75, "defence": 69},
        "driver2": {"name": "Emeka Eze", "nationality": "Nigerian",
                    "pace": 72, "racecraft": 71, "consistency": 60,
                    "wet_weather": 68, "overtaking": 72, "defence": 67},
    },
    {
        "name": "Nova Eleven Racing",
        "personality": "development",
        "tier": 3,
        "lore": "Young driver academy squad — raw talent, rough edges.",
        "strengths": ["aerodynamics"],
        "weakness": "chassis",
        "driver": {"name": "Luca Valentini", "nationality": "Italian",
                   "pace": 76, "racecraft": 74, "consistency": 72,
                   "wet_weather": 71, "overtaking": 77, "defence": 70},
        "driver2": {"name": "Priya Sharma", "nationality": "Indian",
                    "pace": 74, "racecraft": 72, "consistency": 70,
                    "wet_weather": 69, "overtaking": 74, "defence": 68},
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# PERSONALITY → STRATEGY MAPPING
# ─────────────────────────────────────────────────────────────────────────────
PERSONALITY_STRATEGIES = {
    "aggressive":    ["aggressive", "1stop"],
    "calculated":    ["balanced", "conservative"],
    "consistent":    ["conservative", "balanced"],
    "wet_specialist":["balanced", "2stop"],
    "opportunist":   ["aggressive", "2stop", "3stop"],
    "defensive":     ["conservative", "1stop"],
    "erratic":       ["aggressive", "3stop", "balanced", "1stop"],
    "development":   ["balanced", "2stop"],
}

# ─────────────────────────────────────────────────────────────────────────────
# TIER → BASE CAR STATS
# ─────────────────────────────────────────────────────────────────────────────
TIER_BASE_STATS = {
    1: {"engine": 88, "aerodynamics": 87, "chassis": 86, "reliability": 84, "tyre_mgmt": 82, "pit_crew": 85},
    2: {"engine": 75, "aerodynamics": 74, "chassis": 74, "reliability": 76, "tyre_mgmt": 73, "pit_crew": 72},
    3: {"engine": 62, "aerodynamics": 61, "chassis": 60, "reliability": 58, "tyre_mgmt": 59, "pit_crew": 60},
}

STRENGTH_BOOST = 10
WEAKNESS_PENALTY = 12


def build_ai_car_stats(ai_team: dict) -> dict:
    """Return car stats dict for an AI team based on tier + strengths/weakness."""
    stats = dict(TIER_BASE_STATS[ai_team["tier"]])
    for stat in ai_team["strengths"]:
        stats[stat] = min(100, stats[stat] + STRENGTH_BOOST)
    stats[ai_team["weakness"]] = max(30, stats[ai_team["weakness"]] - WEAKNESS_PENALTY)
    # Small random variation each season ±3
    return {k: max(30, min(100, v + random.randint(-3, 3))) for k, v in stats.items()}


def get_ai_strategy(ai_team: dict) -> str:
    """Pick a strategy based on personality, with some randomness."""
    options = PERSONALITY_STRATEGIES.get(ai_team["personality"], ["balanced"])
    # 80% pick from personality pool, 20% random
    if random.random() < 0.20:
        return random.choice(["1stop", "2stop", "3stop", "aggressive", "balanced", "conservative"])
    return random.choice(options)


def get_ai_teams_for_league(count: int, exclude_names: list[str] = None) -> list[dict]:
    """
    Return `count` AI teams (shuffled, no repeats).
    exclude_names: list of team names already in the league.
    """
    exclude_names = set(exclude_names or [])
    available = [t for t in AI_TEAMS if t["name"] not in exclude_names]
    random.shuffle(available)
    return available[:count]
