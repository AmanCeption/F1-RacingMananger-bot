"""
Configuration Management
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


class Settings(BaseSettings):
    # Bot
    BOT_TOKEN: str = Field(..., env="BOT_TOKEN")
    ADMIN_IDS: list[int] = Field(default=[], env="ADMIN_IDS")
    
    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://f1bot:f1bot@localhost:5432/f1bot",
        env="DATABASE_URL"
    )
    
    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    
    # Game Settings
    STARTING_BUDGET: int = Field(default=100_000_000, env="STARTING_BUDGET")
    MAX_TEAMS_PER_LEAGUE: int = Field(default=20, env="MAX_TEAMS_PER_LEAGUE")
    SEASON_RACES: int = Field(default=24, env="SEASON_RACES")
    WEEKLY_RESEARCH_POINTS: int = Field(default=50, env="WEEKLY_RESEARCH_POINTS")
    DAILY_REWARD_MONEY: int = Field(default=500_000, env="DAILY_REWARD_MONEY")
    DAILY_REWARD_RP: int = Field(default=10, env="DAILY_REWARD_RP")
    
    # Race Schedule (UTC)
    RACE_HOUR: int = Field(default=14, env="RACE_HOUR")
    RACE_MINUTE: int = Field(default=0, env="RACE_MINUTE")
    
    # Anti-Cheat
    COMMAND_COOLDOWN: int = Field(default=3, env="COMMAND_COOLDOWN")  # seconds
    MAX_COMMANDS_PER_MINUTE: int = Field(default=20, env="MAX_COMMANDS_PER_MINUTE")
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FILE: str = Field(default="logs/bot.log", env="LOG_FILE")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

# F1 Points System
F1_POINTS = {
    1: 25, 2: 18, 3: 15, 4: 12, 5: 10,
    6: 8, 7: 6, 8: 4, 9: 2, 10: 1
}

# F1 Calendar 2024 Tracks
F1_CALENDAR = [
    {"name": "Bahrain Grand Prix", "circuit": "Bahrain International Circuit", "laps": 57, "country": "🇧🇭"},
    {"name": "Saudi Arabian Grand Prix", "circuit": "Jeddah Corniche Circuit", "laps": 50, "country": "🇸🇦"},
    {"name": "Australian Grand Prix", "circuit": "Albert Park Circuit", "laps": 58, "country": "🇦🇺"},
    {"name": "Japanese Grand Prix", "circuit": "Suzuka International Racing Course", "laps": 53, "country": "🇯🇵"},
    {"name": "Chinese Grand Prix", "circuit": "Shanghai International Circuit", "laps": 56, "country": "🇨🇳"},
    {"name": "Miami Grand Prix", "circuit": "Miami International Autodrome", "laps": 57, "country": "🇺🇸"},
    {"name": "Emilia Romagna Grand Prix", "circuit": "Autodromo Enzo e Dino Ferrari", "laps": 63, "country": "🇮🇹"},
    {"name": "Monaco Grand Prix", "circuit": "Circuit de Monaco", "laps": 78, "country": "🇲🇨"},
    {"name": "Canadian Grand Prix", "circuit": "Circuit Gilles Villeneuve", "laps": 70, "country": "🇨🇦"},
    {"name": "Spanish Grand Prix", "circuit": "Circuit de Barcelona-Catalunya", "laps": 66, "country": "🇪🇸"},
    {"name": "Austrian Grand Prix", "circuit": "Red Bull Ring", "laps": 71, "country": "🇦🇹"},
    {"name": "British Grand Prix", "circuit": "Silverstone Circuit", "laps": 52, "country": "🇬🇧"},
    {"name": "Hungarian Grand Prix", "circuit": "Hungaroring", "laps": 70, "country": "🇭🇺"},
    {"name": "Belgian Grand Prix", "circuit": "Circuit de Spa-Francorchamps", "laps": 44, "country": "🇧🇪"},
    {"name": "Dutch Grand Prix", "circuit": "Circuit Zandvoort", "laps": 72, "country": "🇳🇱"},
    {"name": "Italian Grand Prix", "circuit": "Autodromo Nazionale Monza", "laps": 53, "country": "🇮🇹"},
    {"name": "Azerbaijan Grand Prix", "circuit": "Baku City Circuit", "laps": 51, "country": "🇦🇿"},
    {"name": "Singapore Grand Prix", "circuit": "Marina Bay Street Circuit", "laps": 62, "country": "🇸🇬"},
    {"name": "United States Grand Prix", "circuit": "Circuit of the Americas", "laps": 56, "country": "🇺🇸"},
    {"name": "Mexico City Grand Prix", "circuit": "Autodromo Hermanos Rodriguez", "laps": 71, "country": "🇲🇽"},
    {"name": "São Paulo Grand Prix", "circuit": "Autodromo Jose Carlos Pace", "laps": 71, "country": "🇧🇷"},
    {"name": "Las Vegas Grand Prix", "circuit": "Las Vegas Strip Circuit", "laps": 50, "country": "🇺🇸"},
    {"name": "Qatar Grand Prix", "circuit": "Lusail International Circuit", "laps": 57, "country": "🇶🇦"},
    {"name": "Abu Dhabi Grand Prix", "circuit": "Yas Marina Circuit", "laps": 58, "country": "🇦🇪"},
]

# Tyre Compounds
TYRE_DATA = {
    "soft":  {"pace": 1.0, "wear_rate": 0.035, "color": "🔴"},
    "medium": {"pace": 0.97, "wear_rate": 0.022, "color": "🟡"},
    "hard":  {"pace": 0.94, "wear_rate": 0.014, "color": "⚪"},
    "intermediate": {"pace": 0.90, "wear_rate": 0.025, "color": "🟢"},
    "wet":   {"pace": 0.85, "wear_rate": 0.030, "color": "🔵"},
}
