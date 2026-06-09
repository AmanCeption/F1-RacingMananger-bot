"""
F1 Driver Database
Contains real 2024 F1 drivers + fictional drivers for market depth
"""

# Format: name, nationality, age, number, skill, racecraft, pace, consistency,
#         wet_weather, overtaking, defence, development_potential, base_salary, is_fictional

REAL_DRIVERS = [
    # Top tier
    {"name": "Max Verstappen", "nationality": "Dutch", "age": 26, "number": 1,
     "skill": 98, "racecraft": 98, "pace": 99, "consistency": 97, "wet_weather": 96,
     "overtaking": 97, "defence": 99, "development_potential": 85, "base_salary": 55_000_000},

    {"name": "Lewis Hamilton", "nationality": "British", "age": 39, "number": 44,
     "skill": 97, "racecraft": 98, "pace": 96, "consistency": 95, "wet_weather": 99,
     "overtaking": 96, "defence": 97, "development_potential": 60, "base_salary": 50_000_000},

    {"name": "Fernando Alonso", "nationality": "Spanish", "age": 42, "number": 14,
     "skill": 97, "racecraft": 99, "pace": 94, "consistency": 96, "wet_weather": 98,
     "overtaking": 95, "defence": 99, "development_potential": 45, "base_salary": 20_000_000},

    {"name": "Charles Leclerc", "nationality": "Monégasque", "age": 26, "number": 16,
     "skill": 94, "racecraft": 93, "pace": 96, "consistency": 88, "wet_weather": 92,
     "overtaking": 91, "defence": 89, "development_potential": 88, "base_salary": 25_000_000},

    {"name": "Carlos Sainz", "nationality": "Spanish", "age": 29, "number": 55,
     "skill": 92, "racecraft": 93, "pace": 91, "consistency": 94, "wet_weather": 90,
     "overtaking": 89, "defence": 92, "development_potential": 80, "base_salary": 18_000_000},

    {"name": "Lando Norris", "nationality": "British", "age": 24, "number": 4,
     "skill": 93, "racecraft": 92, "pace": 95, "consistency": 90, "wet_weather": 94,
     "overtaking": 92, "defence": 88, "development_potential": 92, "base_salary": 20_000_000},

    {"name": "George Russell", "nationality": "British", "age": 26, "number": 63,
     "skill": 90, "racecraft": 90, "pace": 92, "consistency": 93, "wet_weather": 91,
     "overtaking": 87, "defence": 90, "development_potential": 90, "base_salary": 15_000_000},

    {"name": "Sergio Perez", "nationality": "Mexican", "age": 34, "number": 11,
     "skill": 88, "racecraft": 90, "pace": 87, "consistency": 89, "wet_weather": 86,
     "overtaking": 88, "defence": 91, "development_potential": 55, "base_salary": 10_000_000},

    {"name": "Oscar Piastri", "nationality": "Australian", "age": 23, "number": 81,
     "skill": 88, "racecraft": 87, "pace": 90, "consistency": 89, "wet_weather": 86,
     "overtaking": 86, "defence": 84, "development_potential": 95, "base_salary": 8_000_000},

    {"name": "Lance Stroll", "nationality": "Canadian", "age": 25, "number": 18,
     "skill": 80, "racecraft": 79, "pace": 81, "consistency": 78, "wet_weather": 85,
     "overtaking": 76, "defence": 80, "development_potential": 75, "base_salary": 8_000_000},

    # Mid tier
    {"name": "Esteban Ocon", "nationality": "French", "age": 27, "number": 31,
     "skill": 83, "racecraft": 83, "pace": 83, "consistency": 84, "wet_weather": 82,
     "overtaking": 80, "defence": 86, "development_potential": 70, "base_salary": 6_000_000},

    {"name": "Pierre Gasly", "nationality": "French", "age": 28, "number": 10,
     "skill": 84, "racecraft": 83, "pace": 85, "consistency": 83, "wet_weather": 84,
     "overtaking": 83, "defence": 82, "development_potential": 72, "base_salary": 6_500_000},

    {"name": "Nico Hulkenberg", "nationality": "German", "age": 36, "number": 27,
     "skill": 84, "racecraft": 86, "pace": 83, "consistency": 87, "wet_weather": 85,
     "overtaking": 82, "defence": 88, "development_potential": 50, "base_salary": 5_000_000},

    {"name": "Kevin Magnussen", "nationality": "Danish", "age": 31, "number": 20,
     "skill": 81, "racecraft": 84, "pace": 80, "consistency": 79, "wet_weather": 80,
     "overtaking": 79, "defence": 87, "development_potential": 55, "base_salary": 3_000_000},

    {"name": "Valtteri Bottas", "nationality": "Finnish", "age": 34, "number": 77,
     "skill": 86, "racecraft": 84, "pace": 87, "consistency": 88, "wet_weather": 86,
     "overtaking": 82, "defence": 85, "development_potential": 52, "base_salary": 5_000_000},

    {"name": "Zhou Guanyu", "nationality": "Chinese", "age": 25, "number": 24,
     "skill": 78, "racecraft": 77, "pace": 79, "consistency": 80, "wet_weather": 77,
     "overtaking": 75, "defence": 78, "development_potential": 82, "base_salary": 2_500_000},

    {"name": "Yuki Tsunoda", "nationality": "Japanese", "age": 24, "number": 22,
     "skill": 82, "racecraft": 83, "pace": 84, "consistency": 78, "wet_weather": 81,
     "overtaking": 84, "defence": 78, "development_potential": 85, "base_salary": 3_000_000},

    {"name": "Daniel Ricciardo", "nationality": "Australian", "age": 34, "number": 3,
     "skill": 88, "racecraft": 91, "pace": 87, "consistency": 83, "wet_weather": 86,
     "overtaking": 93, "defence": 85, "development_potential": 55, "base_salary": 7_000_000},

    {"name": "Alexander Albon", "nationality": "Thai", "age": 28, "number": 23,
     "skill": 84, "racecraft": 83, "pace": 85, "consistency": 85, "wet_weather": 82,
     "overtaking": 81, "defence": 86, "development_potential": 78, "base_salary": 4_000_000},

    {"name": "Logan Sargeant", "nationality": "American", "age": 23, "number": 2,
     "skill": 72, "racecraft": 70, "pace": 73, "consistency": 71, "wet_weather": 70,
     "overtaking": 68, "defence": 72, "development_potential": 80, "base_salary": 1_500_000},
]

FICTIONAL_DRIVERS = [
    # Young talents
    {"name": "Kai Nakamura", "nationality": "Japanese", "age": 20, "is_fictional": True,
     "skill": 82, "racecraft": 80, "pace": 85, "consistency": 78, "wet_weather": 79,
     "overtaking": 83, "defence": 75, "development_potential": 97, "base_salary": 2_000_000},

    {"name": "Mateo Rodrigues", "nationality": "Brazilian", "age": 21, "is_fictional": True,
     "skill": 79, "racecraft": 81, "pace": 82, "consistency": 76, "wet_weather": 80,
     "overtaking": 84, "defence": 72, "development_potential": 95, "base_salary": 1_800_000},

    {"name": "Ethan Clarke", "nationality": "British", "age": 22, "is_fictional": True,
     "skill": 78, "racecraft": 77, "pace": 80, "consistency": 79, "wet_weather": 81,
     "overtaking": 76, "defence": 77, "development_potential": 91, "base_salary": 1_700_000},

    {"name": "Lucas Morel", "nationality": "French", "age": 23, "is_fictional": True,
     "skill": 80, "racecraft": 79, "pace": 81, "consistency": 82, "wet_weather": 78,
     "overtaking": 78, "defence": 80, "development_potential": 88, "base_salary": 2_200_000},

    {"name": "Aleksei Volkov", "nationality": "Russian", "age": 24, "is_fictional": True,
     "skill": 81, "racecraft": 82, "pace": 80, "consistency": 83, "wet_weather": 84,
     "overtaking": 79, "defence": 82, "development_potential": 82, "base_salary": 2_500_000},

    {"name": "Priya Sharma", "nationality": "Indian", "age": 22, "is_fictional": True,
     "skill": 83, "racecraft": 81, "pace": 84, "consistency": 82, "wet_weather": 80,
     "overtaking": 82, "defence": 79, "development_potential": 93, "base_salary": 2_000_000},

    {"name": "Henrik Larsson", "nationality": "Swedish", "age": 25, "is_fictional": True,
     "skill": 84, "racecraft": 83, "pace": 83, "consistency": 85, "wet_weather": 87,
     "overtaking": 80, "defence": 83, "development_potential": 80, "base_salary": 3_200_000},

    {"name": "Marco Ferretti", "nationality": "Italian", "age": 26, "is_fictional": True,
     "skill": 83, "racecraft": 85, "pace": 82, "consistency": 84, "wet_weather": 81,
     "overtaking": 83, "defence": 85, "development_potential": 77, "base_salary": 3_500_000},

    {"name": "Jin-Ho Park", "nationality": "South Korean", "age": 21, "is_fictional": True,
     "skill": 77, "racecraft": 76, "pace": 79, "consistency": 77, "wet_weather": 78,
     "overtaking": 77, "defence": 74, "development_potential": 96, "base_salary": 1_600_000},

    {"name": "Cameron Walsh", "nationality": "Australian", "age": 23, "is_fictional": True,
     "skill": 80, "racecraft": 82, "pace": 81, "consistency": 80, "wet_weather": 79,
     "overtaking": 85, "defence": 76, "development_potential": 87, "base_salary": 2_300_000},

    # Veterans
    {"name": "Raul Espinoza", "nationality": "Mexican", "age": 35, "is_fictional": True,
     "skill": 87, "racecraft": 89, "pace": 85, "consistency": 91, "wet_weather": 86,
     "overtaking": 87, "defence": 90, "development_potential": 40, "base_salary": 5_000_000},

    {"name": "Tom Whitaker", "nationality": "British", "age": 33, "is_fictional": True,
     "skill": 86, "racecraft": 87, "pace": 84, "consistency": 89, "wet_weather": 88,
     "overtaking": 83, "defence": 88, "development_potential": 45, "base_salary": 4_500_000},

    {"name": "Baptiste Girard", "nationality": "French", "age": 32, "is_fictional": True,
     "skill": 85, "racecraft": 86, "pace": 85, "consistency": 87, "wet_weather": 85,
     "overtaking": 82, "defence": 87, "development_potential": 48, "base_salary": 4_000_000},

    {"name": "Nikolai Petrov", "nationality": "Russian", "age": 30, "is_fictional": True,
     "skill": 84, "racecraft": 85, "pace": 83, "consistency": 86, "wet_weather": 83,
     "overtaking": 81, "defence": 86, "development_potential": 60, "base_salary": 3_800_000},

    {"name": "Dmitri Kovacs", "nationality": "Hungarian", "age": 29, "is_fictional": True,
     "skill": 83, "racecraft": 84, "pace": 83, "consistency": 85, "wet_weather": 82,
     "overtaking": 80, "defence": 84, "development_potential": 65, "base_salary": 3_200_000},

    {"name": "Soren Andersen", "nationality": "Danish", "age": 28, "is_fictional": True,
     "skill": 82, "racecraft": 83, "pace": 82, "consistency": 84, "wet_weather": 86,
     "overtaking": 79, "defence": 83, "development_potential": 70, "base_salary": 3_000_000},

    {"name": "Adebayo Okafor", "nationality": "Nigerian", "age": 27, "is_fictional": True,
     "skill": 81, "racecraft": 82, "pace": 82, "consistency": 80, "wet_weather": 79,
     "overtaking": 83, "defence": 78, "development_potential": 75, "base_salary": 2_800_000},

    {"name": "Carlos Mendez", "nationality": "Argentine", "age": 26, "is_fictional": True,
     "skill": 80, "racecraft": 81, "pace": 81, "consistency": 82, "wet_weather": 80,
     "overtaking": 80, "defence": 79, "development_potential": 78, "base_salary": 2_600_000},

    {"name": "Riku Tanaka", "nationality": "Japanese", "age": 25, "is_fictional": True,
     "skill": 81, "racecraft": 80, "pace": 83, "consistency": 81, "wet_weather": 82,
     "overtaking": 81, "defence": 77, "development_potential": 83, "base_salary": 2_500_000},

    {"name": "Oliver Braun", "nationality": "German", "age": 24, "is_fictional": True,
     "skill": 80, "racecraft": 79, "pace": 80, "consistency": 83, "wet_weather": 81,
     "overtaking": 77, "defence": 82, "development_potential": 85, "base_salary": 2_400_000},
]

# Staff Database
STAFF_DATABASE = [
    # ══════════════════════════════════════════
    # TEAM PRINCIPALS (Real Legends)
    # ══════════════════════════════════════════
    {"name": "Toto Wolff", "role": "team_principal", "nationality": "Austrian",
     "skill": 99, "salary": 15_000_000, "performance_bonus": 1.12, "is_real": True, "specialty": "leadership"},
    {"name": "Christian Horner", "role": "team_principal", "nationality": "British",
     "skill": 97, "salary": 14_000_000, "performance_bonus": 1.11, "is_real": True, "specialty": "leadership"},
    {"name": "Frederic Vasseur", "role": "team_principal", "nationality": "French",
     "skill": 91, "salary": 10_000_000, "performance_bonus": 1.07, "is_real": True, "specialty": "driver_development"},
    {"name": "Zak Brown", "role": "team_principal", "nationality": "American",
     "skill": 88, "salary": 9_000_000, "performance_bonus": 1.06, "is_real": True, "specialty": "commercial"},
    {"name": "Andrea Stella", "role": "team_principal", "nationality": "Italian",
     "skill": 93, "salary": 11_000_000, "performance_bonus": 1.08, "is_real": True, "specialty": "engineering"},
    # Fictional TPs
    {"name": "Adrian Clarke", "role": "team_principal", "nationality": "British",
     "skill": 85, "salary": 7_000_000, "performance_bonus": 1.05, "is_real": False, "specialty": "leadership"},
    {"name": "Marco Villanueva", "role": "team_principal", "nationality": "Spanish",
     "skill": 82, "salary": 6_000_000, "performance_bonus": 1.04, "is_real": False, "specialty": "commercial"},
    {"name": "Sophie Laurent", "role": "team_principal", "nationality": "French",
     "skill": 79, "salary": 5_000_000, "performance_bonus": 1.03, "is_real": False, "specialty": "driver_development"},

    # ══════════════════════════════════════════
    # TECHNICAL DIRECTORS (Real Legends)
    # ══════════════════════════════════════════
    {"name": "Adrian Newey", "role": "technical_director", "nationality": "British",
     "skill": 100, "salary": 20_000_000, "performance_bonus": 1.15, "is_real": True, "specialty": "aero"},
    {"name": "James Allison", "role": "technical_director", "nationality": "British",
     "skill": 96, "salary": 14_000_000, "performance_bonus": 1.11, "is_real": True, "specialty": "chassis"},
    {"name": "Enrico Cardile", "role": "technical_director", "nationality": "Italian",
     "skill": 92, "salary": 11_000_000, "performance_bonus": 1.08, "is_real": True, "specialty": "aero"},
    {"name": "Pat Fry", "role": "technical_director", "nationality": "British",
     "skill": 89, "salary": 9_500_000, "performance_bonus": 1.07, "is_real": True, "specialty": "chassis"},
    {"name": "Mike Elliott", "role": "technical_director", "nationality": "British",
     "skill": 87, "salary": 8_500_000, "performance_bonus": 1.06, "is_real": True, "specialty": "power_unit"},
    # Fictional TDs
    {"name": "Dr. Hans Mueller", "role": "technical_director", "nationality": "German",
     "skill": 84, "salary": 7_000_000, "performance_bonus": 1.05, "is_real": False, "specialty": "chassis"},
    {"name": "Akira Yamamoto", "role": "technical_director", "nationality": "Japanese",
     "skill": 81, "salary": 6_000_000, "performance_bonus": 1.04, "is_real": False, "specialty": "aero"},
    {"name": "Elena Kowalski", "role": "technical_director", "nationality": "Polish",
     "skill": 78, "salary": 5_000_000, "performance_bonus": 1.03, "is_real": False, "specialty": "reliability"},

    # ══════════════════════════════════════════
    # CHIEF DESIGNERS (Real Legends)
    # ══════════════════════════════════════════
    {"name": "Rob Marshall", "role": "chief_designer", "nationality": "British",
     "skill": 95, "salary": 10_000_000, "performance_bonus": 1.09, "is_real": True, "specialty": "chassis"},
    {"name": "Luca Furbatto", "role": "chief_designer", "nationality": "Italian",
     "skill": 88, "salary": 7_500_000, "performance_bonus": 1.06, "is_real": True, "specialty": "aero"},
    # Fictional
    {"name": "Chen Wei", "role": "chief_designer", "nationality": "Chinese",
     "skill": 82, "salary": 5_500_000, "performance_bonus": 1.04, "is_real": False, "specialty": "chassis"},
    {"name": "Ingrid Holmgren", "role": "chief_designer", "nationality": "Swedish",
     "skill": 78, "salary": 4_500_000, "performance_bonus": 1.03, "is_real": False, "specialty": "aero"},

    # ══════════════════════════════════════════
    # HEAD OF AERODYNAMICS (Real Legends)
    # ══════════════════════════════════════════
    {"name": "Peter Prodromou", "role": "head_of_aerodynamics", "nationality": "British",
     "skill": 96, "salary": 9_000_000, "performance_bonus": 1.10, "is_real": True, "specialty": "aero"},
    {"name": "Dirk de Beer", "role": "head_of_aerodynamics", "nationality": "South African",
     "skill": 88, "salary": 6_500_000, "performance_bonus": 1.07, "is_real": True, "specialty": "aero"},
    # Fictional
    {"name": "Prof. Yuki Sato", "role": "head_of_aerodynamics", "nationality": "Japanese",
     "skill": 84, "salary": 5_500_000, "performance_bonus": 1.06, "is_real": False, "specialty": "aero"},
    {"name": "Claire Dubois", "role": "head_of_aerodynamics", "nationality": "French",
     "skill": 80, "salary": 4_200_000, "performance_bonus": 1.04, "is_real": False, "specialty": "aero"},
    {"name": "Stefan Richter", "role": "head_of_aerodynamics", "nationality": "German",
     "skill": 76, "salary": 3_500_000, "performance_bonus": 1.03, "is_real": False, "specialty": "aero"},

    # ══════════════════════════════════════════
    # AERODYNAMICIST
    # ══════════════════════════════════════════
    {"name": "Ana Martinez", "role": "aerodynamicist", "nationality": "Spanish",
     "skill": 81, "salary": 2_800_000, "performance_bonus": 1.04, "is_real": False, "specialty": "aero"},
    {"name": "Raj Patel", "role": "aerodynamicist", "nationality": "Indian",
     "skill": 77, "salary": 2_400_000, "performance_bonus": 1.03, "is_real": False, "specialty": "aero"},
    {"name": "Emma Lindqvist", "role": "aerodynamicist", "nationality": "Swedish",
     "skill": 73, "salary": 2_000_000, "performance_bonus": 1.02, "is_real": False, "specialty": "aero"},

    # ══════════════════════════════════════════
    # CHIEF RACE ENGINEERS (Real Legends)
    # ══════════════════════════════════════════
    {"name": "Peter Bonnington", "role": "chief_race_engineer", "nationality": "British",
     "skill": 98, "salary": 8_000_000, "performance_bonus": 1.10, "is_real": True, "specialty": "strategy"},
    {"name": "Gianpiero Lambiase", "role": "chief_race_engineer", "nationality": "Italian",
     "skill": 97, "salary": 7_500_000, "performance_bonus": 1.09, "is_real": True, "specialty": "strategy"},
    {"name": "Riccardo Adami", "role": "chief_race_engineer", "nationality": "Italian",
     "skill": 91, "salary": 5_500_000, "performance_bonus": 1.07, "is_real": True, "specialty": "strategy"},
    {"name": "Tom Stallard", "role": "chief_race_engineer", "nationality": "British",
     "skill": 88, "salary": 4_800_000, "performance_bonus": 1.06, "is_real": True, "specialty": "strategy"},
    # Fictional
    {"name": "Michael Barnes", "role": "chief_race_engineer", "nationality": "British",
     "skill": 84, "salary": 3_800_000, "performance_bonus": 1.05, "is_real": False, "specialty": "strategy"},
    {"name": "Francesca Rossi", "role": "chief_race_engineer", "nationality": "Italian",
     "skill": 79, "salary": 3_000_000, "performance_bonus": 1.04, "is_real": False, "specialty": "strategy"},

    # ══════════════════════════════════════════
    # RACE ENGINEERS
    # ══════════════════════════════════════════
    {"name": "David Kim", "role": "race_engineer", "nationality": "South Korean",
     "skill": 82, "salary": 2_200_000, "performance_bonus": 1.04, "is_real": False, "specialty": "setup"},
    {"name": "Thomas Wagner", "role": "race_engineer", "nationality": "German",
     "skill": 78, "salary": 1_800_000, "performance_bonus": 1.03, "is_real": False, "specialty": "tyres"},
    {"name": "Luis Peralta", "role": "race_engineer", "nationality": "Mexican",
     "skill": 75, "salary": 1_600_000, "performance_bonus": 1.02, "is_real": False, "specialty": "setup"},
    {"name": "Haruto Nakamura", "role": "race_engineer", "nationality": "Japanese",
     "skill": 72, "salary": 1_400_000, "performance_bonus": 1.02, "is_real": False, "specialty": "tyres"},

    # ══════════════════════════════════════════
    # PIT CREW CHIEFS (Real Legends)
    # ══════════════════════════════════════════
    {"name": "Phil Turner", "role": "pit_crew_chief", "nationality": "British",
     "skill": 96, "salary": 3_000_000, "performance_bonus": 1.12, "is_real": True, "specialty": "pit_speed"},
    {"name": "Marcos Azar", "role": "pit_crew_chief", "nationality": "Brazilian",
     "skill": 91, "salary": 2_200_000, "performance_bonus": 1.09, "is_real": True, "specialty": "pit_speed"},
    # Fictional
    {"name": "Big Dave Thompson", "role": "pit_crew_chief", "nationality": "British",
     "skill": 88, "salary": 1_800_000, "performance_bonus": 1.07, "is_real": False, "specialty": "pit_speed"},
    {"name": "Carlos Reyes", "role": "pit_crew_chief", "nationality": "Mexican",
     "skill": 84, "salary": 1_500_000, "performance_bonus": 1.06, "is_real": False, "specialty": "pit_speed"},
    {"name": "Bruno Silva", "role": "pit_crew_chief", "nationality": "Brazilian",
     "skill": 80, "salary": 1_200_000, "performance_bonus": 1.04, "is_real": False, "specialty": "pit_speed"},
    {"name": "Jin-ho Park", "role": "pit_crew_chief", "nationality": "South Korean",
     "skill": 75, "salary": 1_000_000, "performance_bonus": 1.03, "is_real": False, "specialty": "pit_speed"},

    # ══════════════════════════════════════════
    # SPORTING DIRECTORS (Real Legends)
    # ══════════════════════════════════════════
    {"name": "Ron Meadows", "role": "sporting_director", "nationality": "British",
     "skill": 94, "salary": 6_000_000, "performance_bonus": 1.07, "is_real": True, "specialty": "regulations"},
    {"name": "Alan Permane", "role": "sporting_director", "nationality": "British",
     "skill": 90, "salary": 5_000_000, "performance_bonus": 1.06, "is_real": True, "specialty": "strategy"},
    # Fictional
    {"name": "Diego Morales", "role": "sporting_director", "nationality": "Argentine",
     "skill": 83, "salary": 3_800_000, "performance_bonus": 1.04, "is_real": False, "specialty": "regulations"},
    {"name": "Priya Kapoor", "role": "sporting_director", "nationality": "Indian",
     "skill": 78, "salary": 3_200_000, "performance_bonus": 1.03, "is_real": False, "specialty": "strategy"},

    # ══════════════════════════════════════════
    # POWER UNIT DIRECTORS (Real Legends)
    # ══════════════════════════════════════════
    {"name": "Ben Hodgkinson", "role": "power_unit_director", "nationality": "British",
     "skill": 93, "salary": 9_000_000, "performance_bonus": 1.08, "is_real": True, "specialty": "power_unit"},
    {"name": "Yusuke Hasegawa", "role": "power_unit_director", "nationality": "Japanese",
     "skill": 90, "salary": 8_000_000, "performance_bonus": 1.07, "is_real": True, "specialty": "power_unit"},
    # Fictional
    {"name": "Klaus Bergmann", "role": "power_unit_director", "nationality": "German",
     "skill": 85, "salary": 6_000_000, "performance_bonus": 1.05, "is_real": False, "specialty": "power_unit"},
    {"name": "Sven Andersen", "role": "power_unit_director", "nationality": "Finnish",
     "skill": 80, "salary": 5_000_000, "performance_bonus": 1.04, "is_real": False, "specialty": "power_unit"},

    # ══════════════════════════════════════════
    # HEAD OF STRATEGY (Real Legends)
    # ══════════════════════════════════════════
    {"name": "Hannah Schmitz", "role": "head_of_strategy", "nationality": "German",
     "skill": 98, "salary": 7_000_000, "performance_bonus": 1.09, "is_real": True, "specialty": "strategy"},
    {"name": "Bernie Collins", "role": "head_of_strategy", "nationality": "Irish",
     "skill": 92, "salary": 5_500_000, "performance_bonus": 1.07, "is_real": True, "specialty": "strategy"},
    # Fictional
    {"name": "Lucia Romano", "role": "head_of_strategy", "nationality": "Italian",
     "skill": 86, "salary": 4_200_000, "performance_bonus": 1.05, "is_real": False, "specialty": "strategy"},
    {"name": "James Caldwell", "role": "head_of_strategy", "nationality": "Australian",
     "skill": 81, "salary": 3_500_000, "performance_bonus": 1.04, "is_real": False, "specialty": "strategy"},
    {"name": "Mei Lin", "role": "head_of_strategy", "nationality": "Chinese",
     "skill": 76, "salary": 2_800_000, "performance_bonus": 1.03, "is_real": False, "specialty": "strategy"},

    # ══════════════════════════════════════════
    # PERFORMANCE DIRECTORS (Real Legends)
    # ══════════════════════════════════════════
    {"name": "Andrew Shovlin", "role": "performance_director", "nationality": "British",
     "skill": 95, "salary": 8_500_000, "performance_bonus": 1.08, "is_real": True, "specialty": "overall"},
    {"name": "Xevi Pujolar", "role": "performance_director", "nationality": "Spanish",
     "skill": 88, "salary": 6_000_000, "performance_bonus": 1.06, "is_real": True, "specialty": "overall"},
    # Fictional
    {"name": "Viktor Petrov", "role": "performance_director", "nationality": "Russian",
     "skill": 82, "salary": 4_500_000, "performance_bonus": 1.04, "is_real": False, "specialty": "overall"},
    {"name": "Amara Diallo", "role": "performance_director", "nationality": "Senegalese",
     "skill": 77, "salary": 3_800_000, "performance_bonus": 1.03, "is_real": False, "specialty": "overall"},
]


# Sponsor Database
SPONSORS = [
    # Small sponsors
    {"name": "SpeedParts Co.", "tier": "small", "reward": 2_000_000, "target_position": 15, "penalty": 0, "min_reputation": 0},
    {"name": "TurboFuel Energy", "tier": "small", "reward": 1_500_000, "target_position": 18, "penalty": 0, "min_reputation": 0},
    {"name": "RaceGear Pro", "tier": "small", "reward": 1_800_000, "target_position": 16, "penalty": 200_000, "min_reputation": 0},
    {"name": "PitStop Café", "tier": "small", "reward": 1_200_000, "target_position": 20, "penalty": 0, "min_reputation": 0},
    {"name": "FastLap Betting", "tier": "small", "reward": 2_200_000, "target_position": 14, "penalty": 300_000, "min_reputation": 0},

    # Medium sponsors
    {"name": "Kronos Watches", "tier": "medium", "reward": 5_000_000, "target_position": 10, "penalty": 500_000, "min_reputation": 20},
    {"name": "AeroDyne Aviation", "tier": "medium", "reward": 6_000_000, "target_points": 5, "penalty": 800_000, "min_reputation": 25},
    {"name": "TechVision Electronics", "tier": "medium", "reward": 4_500_000, "target_position": 12, "penalty": 400_000, "min_reputation": 20},
    {"name": "GlobalBank Finance", "tier": "medium", "reward": 7_000_000, "target_points": 8, "penalty": 1_000_000, "min_reputation": 30},
    {"name": "Nexus Motors", "tier": "medium", "reward": 5_500_000, "target_position": 8, "penalty": 600_000, "min_reputation": 25},

    # Premium sponsors
    {"name": "Apex Luxury Cars", "tier": "premium", "reward": 15_000_000, "target_position": 3, "penalty": 3_000_000, "min_reputation": 50},
    {"name": "QuantumTech Corp", "tier": "premium", "reward": 12_000_000, "target_position": 5, "penalty": 2_000_000, "min_reputation": 45},
    {"name": "Diamond Energy", "tier": "premium", "reward": 18_000_000, "target_points": 25, "penalty": 4_000_000, "min_reputation": 55},
    {"name": "StarVault Finance", "tier": "premium", "reward": 20_000_000, "target_position": 1, "penalty": 5_000_000, "min_reputation": 60},

    # Title sponsors (win required)
    {"name": "Pinnacle Global", "tier": "title", "reward": 50_000_000, "target_points": 100, "penalty": 10_000_000, "min_reputation": 75},
    {"name": "Sovereign Holdings", "tier": "title", "reward": 40_000_000, "target_position": 1, "penalty": 8_000_000, "min_reputation": 70},
]

# Achievements
ACHIEVEMENTS = [
    {"key": "first_race", "name": "Race Day!", "description": "Complete your first race", "icon": "🏁", "reward_money": 500_000, "reward_rp": 5, "reward_reputation": 2},
    {"key": "first_win", "name": "Winner!", "description": "Win your first race", "icon": "🏆", "reward_money": 5_000_000, "reward_rp": 25, "reward_reputation": 10},
    {"key": "first_pole", "name": "Pole Sitter", "description": "Start from pole position", "icon": "🔴", "reward_money": 1_000_000, "reward_rp": 10, "reward_reputation": 5},
    {"key": "first_podium", "name": "On the Podium!", "description": "Finish on the podium", "icon": "🥇", "reward_money": 2_000_000, "reward_rp": 15, "reward_reputation": 7},
    {"key": "hundred_points", "name": "Century!", "description": "Score 100 championship points", "icon": "💯", "reward_money": 3_000_000, "reward_rp": 20, "reward_reputation": 8},
    {"key": "champion", "name": "CHAMPION!", "description": "Win the Constructors Championship", "icon": "👑", "reward_money": 50_000_000, "reward_rp": 100, "reward_reputation": 25},
    {"key": "driver_champion", "name": "Drivers Champion!", "description": "Your driver wins the WDC", "icon": "🌟", "reward_money": 30_000_000, "reward_rp": 75, "reward_reputation": 20},
    {"key": "hat_trick", "name": "Hat Trick!", "description": "Win 3 races in a row", "icon": "🎩", "reward_money": 10_000_000, "reward_rp": 30, "reward_reputation": 12},
    {"key": "fastest_lap_5", "name": "Speed Demon", "description": "Set 5 fastest laps", "icon": "⚡", "reward_money": 2_000_000, "reward_rp": 15, "reward_reputation": 5},
    {"key": "sponsor_master", "name": "Business Minded", "description": "Sign 5 sponsors in one season", "icon": "💰", "reward_money": 5_000_000, "reward_rp": 20, "reward_reputation": 8},
    {"key": "development_beast", "name": "Innovation Lab", "description": "Max out one car attribute", "icon": "🔬", "reward_money": 3_000_000, "reward_rp": 30, "reward_reputation": 10},
    {"key": "comeback_king", "name": "Comeback King", "description": "Win after starting P15 or lower", "icon": "🦁", "reward_money": 7_000_000, "reward_rp": 35, "reward_reputation": 15},
    {"key": "rain_master", "name": "Rain Master", "description": "Win a race in heavy rain", "icon": "⛈️", "reward_money": 5_000_000, "reward_rp": 25, "reward_reputation": 10},
    {"key": "season_complete", "name": "Full Season", "description": "Complete a full season", "icon": "🗓️", "reward_money": 10_000_000, "reward_rp": 50, "reward_reputation": 15},
]

# Research Trees
RESEARCH_TREES = {
    "power_unit": [
        {"node": "fuel_injection_v1", "name": "Improved Fuel Injection", "rp_cost": 30, "money_cost": 5_000_000, "stat": "engine", "bonus": 3},
        {"node": "turbo_efficiency", "name": "Turbo Efficiency", "rp_cost": 50, "money_cost": 8_000_000, "stat": "engine", "bonus": 4},
        {"node": "hybrid_mguk", "name": "MGU-K Upgrade", "rp_cost": 80, "money_cost": 15_000_000, "stat": "engine", "bonus": 6},
        {"node": "power_boost_evo", "name": "Power Boost EVO", "rp_cost": 120, "money_cost": 25_000_000, "stat": "engine", "bonus": 8},
    ],
    "aero": [
        {"node": "front_wing_v2", "name": "Front Wing V2", "rp_cost": 25, "money_cost": 4_000_000, "stat": "aerodynamics", "bonus": 3},
        {"node": "diffuser_upgrade", "name": "Diffuser Package", "rp_cost": 45, "money_cost": 7_000_000, "stat": "aerodynamics", "bonus": 4},
        {"node": "floor_design", "name": "Revolutionary Floor", "rp_cost": 75, "money_cost": 12_000_000, "stat": "aerodynamics", "bonus": 6},
        {"node": "full_aero_package", "name": "Full Aero Package", "rp_cost": 100, "money_cost": 20_000_000, "stat": "aerodynamics", "bonus": 7},
    ],
    "weight_reduction": [
        {"node": "carbon_fibre_v1", "name": "Carbon Fibre Components", "rp_cost": 30, "money_cost": 6_000_000, "stat": "chassis", "bonus": 3},
        {"node": "titanium_bolts", "name": "Titanium Hardware", "rp_cost": 40, "money_cost": 8_000_000, "stat": "chassis", "bonus": 3},
        {"node": "monocoque_upgrade", "name": "Monocoque Redesign", "rp_cost": 70, "money_cost": 14_000_000, "stat": "chassis", "bonus": 5},
        {"node": "ultra_light_chassis", "name": "Ultra-Light Chassis", "rp_cost": 100, "money_cost": 22_000_000, "stat": "chassis", "bonus": 7},
    ],
    "reliability": [
        {"node": "cooling_v1", "name": "Cooling System Upgrade", "rp_cost": 20, "money_cost": 3_000_000, "stat": "reliability", "bonus": 4},
        {"node": "hydraulics_v2", "name": "Hydraulics V2", "rp_cost": 35, "money_cost": 5_000_000, "stat": "reliability", "bonus": 4},
        {"node": "gearbox_hardening", "name": "Gearbox Hardening", "rp_cost": 55, "money_cost": 9_000_000, "stat": "reliability", "bonus": 5},
        {"node": "zero_failure_protocol", "name": "Zero Failure Protocol", "rp_cost": 90, "money_cost": 18_000_000, "stat": "reliability", "bonus": 8},
    ],
    "tyres": [
        {"node": "tyre_sensors", "name": "Advanced Tyre Sensors", "rp_cost": 20, "money_cost": 2_500_000, "stat": "tyres", "bonus": 3},
        {"node": "compound_analysis", "name": "Compound Analysis", "rp_cost": 35, "money_cost": 4_000_000, "stat": "tyres", "bonus": 4},
        {"node": "thermal_management", "name": "Tyre Thermal Management", "rp_cost": 60, "money_cost": 8_000_000, "stat": "tyres", "bonus": 5},
        {"node": "smart_tyre_system", "name": "Smart Tyre System", "rp_cost": 85, "money_cost": 15_000_000, "stat": "tyres", "bonus": 7},
    ],
}
