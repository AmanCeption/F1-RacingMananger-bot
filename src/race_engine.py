"""
F1 Race Simulation Engine
Simulates full race weekends including Practice, Qualifying, and Race
"""
import random
import math
import logging
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class Weather(str, Enum):
    SUNNY = "sunny"
    CLOUDY = "cloudy"
    LIGHT_RAIN = "light_rain"
    HEAVY_RAIN = "heavy_rain"
    MIXED = "mixed"


WEATHER_LABELS = {
    Weather.SUNNY: "☀️ Sunny",
    Weather.CLOUDY: "🌥️ Cloudy",
    Weather.LIGHT_RAIN: "🌧️ Light Rain",
    Weather.HEAVY_RAIN: "⛈️ Heavy Rain",
    Weather.MIXED: "🌦️ Mixed Conditions",
}

TYRE_PACE = {
    "soft": 1.000, "medium": 0.980, "hard": 0.960,
    "intermediate": 0.910, "wet": 0.870,
}
TYRE_WEAR = {
    "soft": 0.035, "medium": 0.022, "hard": 0.014,
    "intermediate": 0.025, "wet": 0.030,
}
WEATHER_TYRE_BONUS = {
    Weather.SUNNY: {"soft": 1.0, "medium": 1.0, "hard": 1.0, "intermediate": 0.75, "wet": 0.60},
    Weather.CLOUDY: {"soft": 1.0, "medium": 1.0, "hard": 1.0, "intermediate": 0.85, "wet": 0.70},
    Weather.LIGHT_RAIN: {"soft": 0.85, "medium": 0.90, "hard": 0.88, "intermediate": 1.0, "wet": 0.95},
    Weather.HEAVY_RAIN: {"soft": 0.65, "medium": 0.70, "hard": 0.68, "intermediate": 0.90, "wet": 1.0},
    Weather.MIXED: {"soft": 0.92, "medium": 0.96, "hard": 0.94, "intermediate": 0.98, "wet": 0.88},
}


@dataclass
class CarEntry:
    """Represents a car in the race"""
    team_id: int
    team_name: str
    driver_id: int
    driver_name: str

    # Driver skills (0-100)
    pace: int
    racecraft: int
    consistency: int
    wet_weather: int
    overtaking: int
    defence: int

    # Car stats (0-100)
    engine: int
    aerodynamics: int
    chassis: int
    reliability: int
    tyre_mgmt: int  # tyres stat
    pit_crew: int

    # Staff modifiers
    staff_modifier: float = 1.0

    # Strategy
    strategy: str = "balanced"  # 1stop/2stop/3stop/aggressive/balanced/conservative
    current_tyre: str = "medium"
    tyre_age: int = 0
    tyre_wear: float = 0.0
    planned_stops: list = field(default_factory=list)

    # Race state
    position: int = 0
    gap_to_leader: float = 0.0
    lap_time_base: float = 90.0  # seconds
    total_time: float = 0.0
    pit_stops_done: int = 0
    is_dnf: bool = False
    dnf_reason: str = ""
    has_fastest_lap: bool = False
    laps_led: int = 0

    # Setup modifiers (-10 to +10)
    wing_angle: int = 0
    suspension: int = 0
    tyre_pressure: int = 0
    gear_ratio: int = 0


def generate_weather() -> Weather:
    weights = {
        Weather.SUNNY: 0.40,
        Weather.CLOUDY: 0.25,
        Weather.LIGHT_RAIN: 0.15,
        Weather.HEAVY_RAIN: 0.08,
        Weather.MIXED: 0.12,
    }
    return random.choices(list(weights.keys()), weights=list(weights.values()))[0]


def calculate_base_laptime(car: CarEntry, weather: Weather) -> float:
    """Calculate base lap time in seconds. Lower = faster"""
    # Car performance (avg of key stats)
    car_perf = (car.engine * 0.25 + car.aerodynamics * 0.20 +
                car.chassis * 0.20 + car.reliability * 0.10 +
                car.tyre_mgmt * 0.15 + car.pit_crew * 0.10)

    # Driver performance
    driver_perf = (car.pace * 0.30 + car.racecraft * 0.20 +
                   car.consistency * 0.25 + car.wet_weather * 0.25
                   if weather in [Weather.LIGHT_RAIN, Weather.HEAVY_RAIN]
                   else car.pace * 0.40 + car.racecraft * 0.30 + car.consistency * 0.30)

    # Combined performance score (0-100)
    total_perf = (car_perf * 0.55 + driver_perf * 0.45) * car.staff_modifier

    # Base time: 100 perf = 85s, 50 perf = 92s, 0 perf = 100s
    base = 100.0 - (total_perf * 0.15)

    # Tyre effect
    tyre_pace = TYRE_PACE[car.current_tyre]
    weather_bonus = WEATHER_TYRE_BONUS[weather][car.current_tyre]
    tyre_effect = tyre_pace * weather_bonus

    # Wear degradation
    degradation = car.tyre_wear * (1.0 + (100 - car.tyre_mgmt) / 200)
    tyre_time_penalty = degradation * 8.0  # seconds per lap added by wear

    # Setup effects
    setup_effect = (car.wing_angle * -0.03 + car.suspension * -0.02 +
                    car.tyre_pressure * -0.01 + car.gear_ratio * -0.02)

    final_time = (base / tyre_effect) + tyre_time_penalty + setup_effect

    # Random lap variance
    variance = random.gauss(0, 0.3)
    return max(70.0, final_time + variance)


def get_dnf_probability(car: CarEntry, lap: int, total_laps: int) -> float:
    """Per-lap DNF probability"""
    base_prob = 0.003  # 0.3% per lap base

    # Reliability reduces failure
    reliability_factor = (100 - car.reliability) / 2000.0

    # Increases near end of race (stress)
    race_progress = lap / total_laps
    stress_factor = race_progress * 0.002

    return base_prob + reliability_factor + stress_factor


def decide_pit_stop(car: CarEntry, lap: int, total_laps: int, weather: Weather,
                    safety_car: bool) -> bool:
    """Decide if car should pit this lap"""
    laps_remaining = total_laps - lap

    # Forced pit if tyre wear > 85%
    if car.tyre_wear >= 0.85:
        return True

    # Safety car opportunity
    if safety_car and car.tyre_age > 15 and car.pit_stops_done < get_max_stops(car.strategy):
        return True

    # Planned stop windows based on strategy
    planned_stops = get_stop_laps(car.strategy, total_laps)
    for stop_lap in planned_stops:
        if abs(lap - stop_lap) <= 2 and car.pit_stops_done < planned_stops.index(stop_lap) + 1:
            return True

    return False


def get_max_stops(strategy: str) -> int:
    return {"1stop": 1, "2stop": 2, "3stop": 3,
            "aggressive": 3, "balanced": 2, "conservative": 1}.get(strategy, 2)


def get_stop_laps(strategy: str, total_laps: int) -> list:
    if strategy in ["1stop", "conservative"]:
        return [int(total_laps * 0.50)]
    elif strategy in ["2stop", "balanced"]:
        return [int(total_laps * 0.33), int(total_laps * 0.66)]
    else:  # 3stop / aggressive
        return [int(total_laps * 0.25), int(total_laps * 0.50), int(total_laps * 0.75)]


def choose_next_tyre(car: CarEntry, weather: Weather, laps_remaining: int) -> str:
    if weather == Weather.HEAVY_RAIN:
        return "wet"
    if weather == Weather.LIGHT_RAIN:
        return "intermediate"

    if laps_remaining <= 15:
        return "soft"
    elif laps_remaining <= 30:
        return "medium"
    else:
        return "hard" if car.strategy == "conservative" else "medium"


def simulate_overtake(attacker: CarEntry, defender: CarEntry, weather: Weather) -> bool:
    """Determine if attacker can overtake defender"""
    attack_score = attacker.overtaking * 0.5 + attacker.pace * 0.3 + attacker.racecraft * 0.2
    defend_score = defender.defence * 0.5 + defender.consistency * 0.3 + defender.racecraft * 0.2

    # Car performance gap
    att_car = (attacker.engine + attacker.aerodynamics) / 2
    def_car = (defender.engine + defender.aerodynamics) / 2
    car_gap = att_car - def_car

    # Time gap effect (DRS-like)
    gap_bonus = max(0, (1.0 - attacker.gap_to_leader) * 20)

    total_attack = attack_score + car_gap * 0.3 + gap_bonus + random.gauss(0, 10)
    total_defend = defend_score + random.gauss(0, 10)

    return total_attack > total_defend


async def simulate_race(
    entries: list[CarEntry],
    circuit_name: str,
    total_laps: int,
    weather: Weather | None = None,
) -> dict:
    """
    Full race simulation.
    Returns: {
        results: [...],    # sorted by finish position
        events: [...],     # lap-by-lap events
        weather: Weather,
        fastest_lap_driver: str,
        fastest_lap_time: float,
    }
    """
    if weather is None:
        weather = generate_weather()

    events = []
    sc_active = False
    vsc_active = False
    red_flag_used = False
    sc_laps_remaining = 0

    # Initialize
    for i, car in enumerate(entries):
        car.position = i + 1
        car.tyre_wear = 0.0
        car.tyre_age = 0
        car.pit_stops_done = 0
        car.is_dnf = False
        car.total_time = 0.0

    events.append(f"🏁 <b>{circuit_name}</b> — {WEATHER_LABELS[weather]}")
    events.append(f"🚦 Lights out! Race STARTED!")

    fastest_lap = float("inf")
    fastest_lap_holder = None

    active_cars = list(entries)

    for lap in range(1, total_laps + 1):
        lap_events = []

        # Weather change mid-race
        if lap == total_laps // 3 and weather == Weather.MIXED:
            weather = random.choice([Weather.LIGHT_RAIN, Weather.SUNNY])
            lap_events.append(f"🌦️ Lap {lap}: Weather changing to {WEATHER_LABELS[weather]}!")

        # Safety car
        if not sc_active and not vsc_active:
            sc_chance = 0.04  # 4% per lap
            if random.random() < sc_chance:
                sc_active = True
                sc_laps_remaining = random.randint(3, 7)
                lap_events.append(f"🟡 Lap {lap}: SAFETY CAR deployed!")
        
        if sc_active:
            sc_laps_remaining -= 1
            if sc_laps_remaining <= 0:
                sc_active = False
                lap_events.append(f"🟢 Lap {lap}: Safety Car returning to pits. GREEN FLAG!")

        # VSC check
        if not sc_active and not vsc_active and random.random() < 0.02:
            vsc_active = True
            vsc_laps = random.randint(1, 3)
            lap_events.append(f"🟡 Lap {lap}: VIRTUAL SAFETY CAR deployed!")

        # Red flag (very rare)
        if not red_flag_used and lap > 5 and random.random() < 0.005:
            red_flag_used = True
            lap_events.append(f"🔴 Lap {lap}: RED FLAG! Race suspended!")
            lap_events.append(f"🔴 Race restarted under safety car conditions.")

        for car in list(active_cars):
            if car.is_dnf:
                continue

            # DNF check
            dnf_prob = get_dnf_probability(car, lap, total_laps)
            if random.random() < dnf_prob:
                car.is_dnf = True
                reasons = [
                    "Engine failure 🔧", "Gearbox issue ⚙️", "Hydraulics failure 💧",
                    "Tyre puncture 💥", "Collision damage 💥", "Brake failure 🛑",
                    "Suspension damage 🔩", "Power unit failure ⚡",
                ]
                car.dnf_reason = random.choice(reasons)
                active_cars.remove(car)
                lap_events.append(f"💥 Lap {lap}: {car.driver_name} ({car.team_name}) — RETIREMENT! {car.dnf_reason}")
                continue

            # Pit stop decision
            if decide_pit_stop(car, lap, total_laps, weather, sc_active):
                old_tyre = car.current_tyre
                car.current_tyre = choose_next_tyre(car, weather, total_laps - lap)
                car.tyre_wear = 0.0
                car.tyre_age = 0
                car.pit_stops_done += 1

                # Pit stop time (based on pit crew)
                pit_time = random.gauss(25.0 - car.pit_crew * 0.1, 1.5)
                pit_error = ""
                if random.random() < 0.05:  # 5% pit error
                    pit_time += random.uniform(3, 8)
                    pit_error = " ⚠️ Slow pit stop!"

                car.total_time += pit_time
                lap_events.append(
                    f"🔧 Lap {lap}: {car.driver_name} pits — {old_tyre.title()} → {car.current_tyre.title()}{pit_error}"
                )

            # Update tyre
            car.tyre_wear = min(1.0, car.tyre_wear + TYRE_WEAR[car.current_tyre])
            car.tyre_age += 1

            # Lap time
            lap_time = calculate_base_laptime(car, weather)
            if sc_active or vsc_active:
                lap_time *= 1.25  # slower behind SC

            car.total_time += lap_time

            # Fastest lap tracking
            if lap_time < fastest_lap:
                fastest_lap = lap_time
                fastest_lap_holder = car

        # Sort positions
        def sort_key(c):
            return (1 if c.is_dnf else 0, c.total_time)

        active_cars.sort(key=lambda c: c.total_time)
        all_sorted = sorted(entries, key=sort_key)

        # Assign positions
        for i, car in enumerate(all_sorted):
            if not car.is_dnf:
                if i == 0:
                    car.laps_led += 1
                car.position = i + 1
                if i > 0:
                    car.gap_to_leader = all_sorted[i].total_time - all_sorted[0].total_time

        # Overtake events (every few laps)
        if lap % 3 == 0 and not sc_active:
            for i in range(len(active_cars) - 1):
                if random.random() < 0.3:
                    attacker = active_cars[i + 1]
                    defender = active_cars[i]
                    if simulate_overtake(attacker, defender, weather):
                        # Swap times (overtake)
                        attacker.total_time, defender.total_time = (
                            defender.total_time + 0.1, attacker.total_time
                        )
                        if random.random() < 0.3:
                            lap_events.append(
                                f"⚡ Lap {lap}: {attacker.driver_name} overtakes {defender.driver_name}!"
                            )

        # Special lap events
        if lap == total_laps // 2:
            leader = active_cars[0] if active_cars else None
            if leader:
                lap_events.append(f"🔄 Lap {lap}: Halfway point! Leader: {leader.driver_name}")

        if lap == total_laps - 5:
            lap_events.append(f"⚡ Lap {lap}: 5 laps remaining!")

        if lap_events:
            events.extend(lap_events)

        if vsc_active:
            vsc_active = False

    # Final sort
    def final_sort_key(c):
        return (1 if c.is_dnf else 0, c.total_time)

    final_order = sorted(entries, key=final_sort_key)
    for i, car in enumerate(final_order):
        car.position = i + 1

    # Fastest lap
    if fastest_lap_holder and not fastest_lap_holder.is_dnf:
        fastest_lap_holder.has_fastest_lap = True
        events.append(
            f"⚡ Fastest Lap: {fastest_lap_holder.driver_name} — {fastest_lap:.3f}s"
        )

    events.append(f"\n🏆 <b>RACE FINISHED!</b>")
    events.append(f"🥇 Winner: <b>{final_order[0].driver_name}</b> ({final_order[0].team_name})")
    if len(final_order) > 1:
        events.append(f"🥈 P2: {final_order[1].driver_name} (+{final_order[1].gap_to_leader:.3f}s)")
    if len(final_order) > 2:
        events.append(f"🥉 P3: {final_order[2].driver_name} (+{final_order[2].gap_to_leader:.3f}s)")

    return {
        "results": final_order,
        "events": events,
        "weather": weather,
        "fastest_lap_driver": fastest_lap_holder.driver_name if fastest_lap_holder else None,
        "fastest_lap_time": fastest_lap if fastest_lap < float("inf") else None,
        "total_laps": total_laps,
        "circuit": circuit_name,
    }


async def simulate_qualifying(entries: list[CarEntry], weather: Weather) -> list[CarEntry]:
    """Simulate qualifying - returns sorted grid"""
    quali_times = []

    for car in entries:
        # Q lap time calculation
        car_perf = (car.engine * 0.3 + car.aerodynamics * 0.3 + car.chassis * 0.2 + car.pit_crew * 0.2)
        driver_perf = car.pace * 0.6 + car.consistency * 0.4

        # Best lap (3 attempts, take fastest)
        best_time = float("inf")
        for _ in range(3):
            weather_factor = WEATHER_TYRE_BONUS[weather]["soft"]
            base = 95.0 - (car_perf * 0.5 + driver_perf * 0.5) * 0.15
            base *= weather_factor
            lap = base + random.gauss(0, 0.4)
            best_time = min(best_time, lap)

        quali_times.append((car, best_time))

    # Sort by time
    quali_times.sort(key=lambda x: x[1])

    sorted_cars = []
    for pos, (car, time) in enumerate(quali_times):
        car.position = pos + 1
        sorted_cars.append(car)

    return sorted_cars


def generate_practice_report(car: CarEntry, weather: Weather) -> str:
    """Generate engineering report from practice session"""
    issues = []
    recommendations = []

    if car.tyre_mgmt < 60:
        issues.append("⚠️ High tyre degradation detected on rear axle")
        recommendations.append("Increase tyre pressure by 1.5 PSI")

    if car.aerodynamics < 55:
        issues.append("⚠️ Understeer present in medium-speed corners")
        recommendations.append("Increase front wing angle by 2°")

    if car.engine < 55:
        issues.append("⚠️ Power unit showing thermal stress")
        recommendations.append("Reduce engine mode to FLOW in sector 2")

    if car.chassis < 55:
        issues.append("⚠️ Oversteer on corner exit")
        recommendations.append("Soften rear suspension")

    if car.reliability < 55:
        issues.append("⚠️ Hydraulics pressure fluctuations detected")

    if not issues:
        issues.append("✅ Car balance nominal")
        recommendations.append("Minor setup refinements only")

    weather_note = {
        Weather.LIGHT_RAIN: "🌧️ Rain expected — consider early switch to intermediates",
        Weather.HEAVY_RAIN: "⛈️ Full wets required — setup change recommended",
        Weather.MIXED: "🌦️ Mixed conditions — be ready to change strategy",
    }.get(weather, "")

    report = "📊 <b>Engineering Report — Practice Session</b>\n\n"
    report += "<b>Issues Found:</b>\n" + "\n".join(f"  {i}" for i in issues)
    report += "\n\n<b>Recommendations:</b>\n" + "\n".join(f"  • {r}" for r in recommendations)
    if weather_note:
        report += f"\n\n{weather_note}"

    return report
