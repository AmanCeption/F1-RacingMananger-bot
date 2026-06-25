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

try:
    from src.core.config import CIRCUIT_DNA
except ImportError:
    CIRCUIT_DNA = {}


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


def calculate_base_laptime(car: CarEntry, weather: Weather, dna: dict | None = None) -> float:
    """Calculate base lap time in seconds. Lower = faster. dna = CIRCUIT_DNA entry."""
    dna = dna or {}
    engine_mod  = dna.get("engine_mod", 1.0)
    tyre_stress = dna.get("tyre_stress", 1.0)

    # Car performance — engine boosted/penalised by circuit DNA
    car_perf = (car.engine * 0.25 * engine_mod + car.aerodynamics * 0.20 +
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
    degradation = car.tyre_wear * (1.0 + (100 - car.tyre_mgmt) / 200) * tyre_stress
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


def simulate_overtake(attacker: CarEntry, defender: CarEntry, weather: Weather, overtaking_mod: float = 1.0) -> bool:
    """Determine if attacker can overtake defender"""
    attack_score = attacker.overtaking * 0.5 + attacker.pace * 0.3 + attacker.racecraft * 0.2
    defend_score = defender.defence * 0.5 + defender.consistency * 0.3 + defender.racecraft * 0.2

    # Car performance gap
    att_car = (attacker.engine + attacker.aerodynamics) / 2
    def_car = (defender.engine + defender.aerodynamics) / 2
    car_gap = att_car - def_car

    # Time gap effect (DRS-like)
    gap_bonus = max(0, (1.0 - attacker.gap_to_leader) * 20)

    total_attack = (attack_score + car_gap * 0.3 + gap_bonus + random.gauss(0, 10)) * overtaking_mod
    total_defend = defend_score + random.gauss(0, 10)

    return total_attack > total_defend


def simulate_race(
    entries: list[CarEntry],
    circuit_name: str,
    total_laps: int,
    weather: Weather | None = None,
    race_name: str = "",
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

    # Circuit DNA — traits that affect simulation
    dna = CIRCUIT_DNA.get(race_name, {})
    overtaking_mod = dna.get("overtaking_mod", 1.0)

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
            lap_time = calculate_base_laptime(car, weather, dna)
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
                    if simulate_overtake(attacker, defender, weather, overtaking_mod):
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


def _calc_quali_lap(car: CarEntry, weather: Weather, tyre: str, attempts: int = 3) -> float:
    """Calculate best qualifying lap time for a car on a given tyre compound."""
    car_perf = (
        car.engine      * 0.28 +
        car.aerodynamics * 0.30 +
        car.chassis      * 0.22 +
        car.pit_crew     * 0.10 +
        car.tyre_mgmt    * 0.10
    )
    # In rain, wet_weather skill matters a lot
    if weather in (Weather.HEAVY_RAIN, Weather.LIGHT_RAIN, Weather.MIXED):
        driver_perf = car.pace * 0.35 + car.consistency * 0.25 + car.wet_weather * 0.40
    else:
        driver_perf = car.pace * 0.55 + car.consistency * 0.30 + car.racecraft * 0.15

    combined = (car_perf * 0.55 + driver_perf * 0.45) * car.staff_modifier

    # Weather × tyre compound interaction
    weather_tyre = WEATHER_TYRE_BONUS[weather][tyre]
    tyre_pace    = TYRE_PACE[tyre]

    # Base time: best car (100) ≈ 82 s, average (50) ≈ 89 s
    base = 91.0 - combined * 0.09
    base = base / (tyre_pace * weather_tyre)

    # Random variance shrinks on faster compounds (driver wrings more out)
    variance_sigma = 0.20 if tyre == "soft" else 0.30

    best = float("inf")
    for _ in range(attempts):
        lap = base + random.gauss(0, variance_sigma)
        best = min(best, lap)
    return best


def simulate_qualifying(
    entries: list[CarEntry],
    weather: Weather,
    circuit_name: str = "Circuit",
) -> dict:
    """
    Dynamic F1-style qualifying that scales to any grid size.

    Elimination rules (based on real F1 proportions):
      - Q1: eliminate ~20% of the field (min 1), rest advance to Q2
      - Q2: eliminate ~30% of Q1 survivors (min 1), rest advance to Q3
      - Q3: everyone left (max 10) fights for pole

    With very small grids:
      - 1-2 cars  → single shootout only (Q3-style, no elimination)
      - 3-5 cars  → Q2 + Q3 (skip Q1)
      - 6+  cars  → full Q1 + Q2 + Q3
    """
    n = len(entries)
    events = []
    q_times: dict[int, dict] = {e.driver_id: {"q1": None, "q2": None, "q3": None} for e in entries}

    events.append(f"🏎️ <b>QUALIFYING — {circuit_name}</b>")
    events.append(f"🌤️ Conditions: {WEATHER_LABELS[weather]}")
    events.append("")

    def _tyre_for_weather(w: Weather) -> str:
        if w in (Weather.SUNNY, Weather.CLOUDY):
            return "soft"
        if w == Weather.LIGHT_RAIN:
            return "intermediate"
        if w == Weather.HEAVY_RAIN:
            return "wet"
        return "medium"  # MIXED

    tyre = _tyre_for_weather(weather)

    # ── Decide format based on grid size ─────────────────────────────────────
    if n <= 2:
        # Tiny grid — single shootout, everyone goes straight to "Q3"
        run_q1 = False
        run_q2 = False
    elif n <= 5:
        # Small grid — skip Q1, run Q2 → Q3
        run_q1 = False
        run_q2 = True
    else:
        run_q1 = True
        run_q2 = True

    q1_survivors = list(entries)  # default: everyone advances if Q1 skipped
    q2_survivors = list(entries)  # default: everyone advances if Q2 skipped

    # ── Q1 ────────────────────────────────────────────────────────────────────
    if run_q1:
        q1_elim = max(1, round(n * 0.20))   # eliminate ~20 %, at least 1
        q1_adv  = n - q1_elim

        events.append(f"⏱️ <b>Q1 — All {n} cars on track</b>")
        q1_results = []
        for car in entries:
            t = _calc_quali_lap(car, weather, tyre)
            q_times[car.driver_id]["q1"] = round(t, 3)
            q1_results.append((car, t))

        q1_results.sort(key=lambda x: x[1])
        for pos, (car, t) in enumerate(q1_results):
            m, s = divmod(t, 60)
            events.append(f"  P{pos+1:>2}  {car.driver_name:<22} {int(m)}:{s:06.3f}")

        q1_out = [car for car, _ in q1_results[q1_adv:]]
        q1_survivors = [car for car, _ in q1_results[:q1_adv]]
        if q1_out:
            events.append(f"\n❌ <b>Out in Q1:</b> " + ", ".join(c.driver_name for c in q1_out))
    else:
        q1_survivors = list(entries)
        if n > 2:
            events.append(f"ℹ️ <b>Q1 skipped</b> — only {n} cars entered, starting from Q2")

    # ── Q2 ────────────────────────────────────────────────────────────────────
    if run_q2:
        n2 = len(q1_survivors)
        q2_elim = max(1, round(n2 * 0.30))   # eliminate ~30 % of Q2 field
        q2_adv  = n2 - q2_elim
        q2_adv  = max(q2_adv, min(n2, 2))     # at least 2 in Q3 (unless only 1 entered)

        events.append(f"\n⏱️ <b>Q2 — {n2} cars fight for Q3</b>")
        q2_results = []
        for car in q1_survivors:
            t = _calc_quali_lap(car, weather, tyre, attempts=3) * random.uniform(0.994, 0.999)
            q_times[car.driver_id]["q2"] = round(t, 3)
            q2_results.append((car, t))

        q2_results.sort(key=lambda x: x[1])
        for pos, (car, t) in enumerate(q2_results):
            m, s = divmod(t, 60)
            events.append(f"  P{pos+1:>2}  {car.driver_name:<22} {int(m)}:{s:06.3f}")

        q2_out = [car for car, _ in q2_results[q2_adv:]]
        q2_survivors = [car for car, _ in q2_results[:q2_adv]]
        if q2_out:
            events.append(f"\n❌ <b>Out in Q2:</b> " + ", ".join(c.driver_name for c in q2_out))
    else:
        q2_survivors = list(q1_survivors)

    # ── Q3 — everyone left, max 10 ────────────────────────────────────────────
    q3_cars = q2_survivors[:10]   # cap at 10 in case somehow more slipped through
    n3 = len(q3_cars)

    q3_tyre = "soft" if weather in (Weather.SUNNY, Weather.CLOUDY) else (
              "intermediate" if weather == Weather.LIGHT_RAIN else "wet")

    events.append(f"\n⏱️ <b>Q3 — POLE SHOOTOUT ({n3} cars)</b>")
    q3_results = []
    for car in q3_cars:
        t = _calc_quali_lap(car, weather, q3_tyre, attempts=2) * random.uniform(0.990, 0.997)
        q_times[car.driver_id]["q3"] = round(t, 3)
        q3_results.append((car, t))

    q3_results.sort(key=lambda x: x[1])
    pole_time   = q3_results[0][1] if q3_results else 90.0
    pole_sitter = q3_results[0][0] if q3_results else entries[0]

    for pos, (car, t) in enumerate(q3_results):
        m, s = divmod(t, 60)
        gap = f"+{t - pole_time:.3f}s" if pos > 0 else "POLE"
        events.append(f"  P{pos+1:>2}  {car.driver_name:<22} {int(m)}:{s:06.3f}  {gap}")

    # ── Final grid: Q3 order → Q2 eliminated → Q1 eliminated ────────────────
    q2_eliminated = [car for car, _ in q2_results[q2_adv:]] if run_q2 else []
    q1_eliminated = [car for car, _ in q1_results[q1_adv:]] if run_q1 else []

    grid_order = (
        [car for car, _ in q3_results] +
        q2_eliminated +
        q1_eliminated
    )

    for i, car in enumerate(grid_order):
        car.position = i + 1

    pm, ps = divmod(pole_time, 60)
    events.append(f"\n🏆 <b>POLE POSITION: {pole_sitter.driver_name}</b>  {int(pm)}:{ps:06.3f}")
    events.append(f"   ({pole_sitter.team_name})")

    if len(q3_results) >= 2:
        gap_to_pole = q3_results[-1][1] - pole_time
        if gap_to_pole > 1.5:
            events.append(f"\n💡 Tip: Large gap to pole — focus on Engine & Aero upgrades")
        elif gap_to_pole > 0.8:
            events.append(f"\n💡 Tip: Moderate gap — driver skill and chassis tuning can help")
        else:
            events.append(f"\n💡 Tip: You're competitive — tyre strategy will be key in the race")

    return {
        "grid": grid_order,
        "q_times": q_times,
        "events": events,
        "weather": weather,
        "pole_time": pole_time,
        "pole_sitter": pole_sitter.driver_name,
    }



def generate_practice_report(
    car: CarEntry,
    weather: Weather,
    race_name: str = "",
    circuit_name: str = "",
    staff_list: list = None,   # list of (TeamStaff, Staff) tuples
) -> str:
    """
    Generate a fully dynamic engineering report for the practice session.
    Every report is circuit-specific, weather-sensitive, stat-driven, and
    enriched by any hired staff. No two reports feel the same.
    """
    import random
    dna = CIRCUIT_DNA.get(race_name, {})
    tyre_stress   = dna.get("tyre_stress", 1.0)
    engine_mod    = dna.get("engine_mod", 1.0)
    overtaking_mod = dna.get("overtaking_mod", 1.0)
    is_wet_volatile = dna.get("weather_volatile", False)
    circuit_note   = dna.get("note", "")

    issues = []
    recs = []

    # ── Tyre issues (amplified by circuit tyre stress) ──────────────────
    tyre_threshold = 65 if tyre_stress >= 1.1 else 55
    if car.tyre_mgmt < tyre_threshold:
        psi = round(random.uniform(1.0, 2.5), 1)
        issues.append(f"⚠️ High tyre degradation on rear axle — stress index {tyre_stress:.1f}x at this circuit")
        recs.append(f"Increase tyre pressure by {psi} PSI; consider harder compound for race")
    elif car.tyre_mgmt >= 75 and tyre_stress >= 1.1:
        issues.append(f"✅ Tyre management strong despite demanding circuit (stress {tyre_stress:.1f}x)")
        recs.append("Stay on current setup — tyre delta over rivals is an asset here")

    # ── Aero issues (circuit-specific) ──────────────────────────────────
    if overtaking_mod <= 0.5:                 # Monaco / Hungary style
        if car.aerodynamics < 70:
            issues.append("⚠️ Insufficient downforce for slow-speed corners — critical on this circuit")
            recs.append("Maximise front and rear wing angles — qualifying position everything here")
        else:
            issues.append("✅ Aero balance good for slow-speed circuit")
            recs.append("Maintain high-downforce setup; small front wing trim for sector 2 hairpin")
    elif engine_mod >= 1.2:                   # Monza / Baku power circuits
        if car.aerodynamics > 70:
            issues.append("⚠️ Too much drag detected — top speed deficit on power straights")
            recs.append("Reduce rear wing angle by 3–4° for straight-line speed; low-drag trim")
        else:
            issues.append("✅ Low-drag setup suits this power circuit")
            recs.append("Fine-tune DRS efficiency; prioritise engine deployment over aero")
    else:
        if car.aerodynamics < 55:
            issues.append("⚠️ Understeer in medium-speed corners — aero deficit")
            recs.append("Increase front wing angle by 2°; check front splitter ride height")

    # ── Engine / Power Unit ──────────────────────────────────────────────
    pu_threshold = 60 if engine_mod >= 1.1 else 50
    if car.engine < pu_threshold:
        mode = random.choice(["sector 2 deployment", "full-race ERS harvesting", "turbo mapping"])
        issues.append(f"⚠️ Power unit thermal stress detected — engine_mod {engine_mod:.2f}x at this circuit")
        recs.append(f"Reduce engine mode to FLOW; prioritise {mode} efficiency")
    elif car.engine >= 75 and engine_mod >= 1.1:
        issues.append("✅ Power unit performing well on a power-sensitive circuit")
        recs.append("Hold engine mode — straight-line advantage can be leveraged in qualifying")

    # ── Chassis / Balance ────────────────────────────────────────────────
    if car.chassis < 55:
        corner_type = "low-speed" if overtaking_mod <= 0.7 else "high-speed"
        issues.append(f"⚠️ Oversteer on corner exit — {corner_type} sections affected")
        recs.append("Soften rear suspension; increase rear ARB stiffness by one click")
    elif car.chassis >= 75:
        issues.append("✅ Chassis balance optimal — strong platform for this circuit")

    # ── Reliability ──────────────────────────────────────────────────────
    if car.reliability < 55:
        component = random.choice([
            "hydraulics pressure fluctuations",
            "gearbox oil temperature spike",
            "MGU-K harvesting anomaly",
            "brake-by-wire calibration drift",
        ])
        issues.append(f"⚠️ {component.capitalize()} detected in data")
        recs.append("Flag to PU team overnight; run reliability mode if issue persists in qualifying")

    # ── Weather-specific insights ────────────────────────────────────────
    weather_section = ""
    if weather == Weather.HEAVY_RAIN:
        tyre_rec = "full wets immediately"
        weather_section = (
            f"⛈️ <b>Weather Alert — Heavy Rain</b>\n"
            f"  • Start on {tyre_rec}; switch to intermediates only if track dries sector by sector\n"
            f"  • Wet weather skill: {car.wet_weather}/100 — "
            + ("driver handles rain well ✅" if car.wet_weather >= 65 else "consider conservative strategy ⚠️")
        )
    elif weather == Weather.LIGHT_RAIN:
        weather_section = (
            f"🌧️ <b>Weather Note — Light Rain</b>\n"
            f"  • Intermediates likely optimal — monitor sector times for slick window\n"
            f"  • Wet weather skill: {car.wet_weather}/100 — "
            + ("driver comfortable in mixed conditions ✅" if car.wet_weather >= 60 else "stay defensive on strategy ⚠️")
        )
    elif weather == Weather.MIXED:
        weather_section = (
            f"🌦️ <b>Weather Note — Mixed Conditions</b>\n"
            f"  • Keep both inter and slick sets warm on the blankets\n"
            f"  • Reactive strategy will be key — brief your Race Engineer on switch triggers"
            + ("\n  • {'Circuit is known for volatile weather — expect multiple changes' if is_wet_volatile else ''}")
        )
    elif is_wet_volatile:
        weather_section = "🌤️ <b>Weather Watch:</b> Circuit historically prone to sudden showers — monitor closely"

    # ── Fallback if no issues ────────────────────────────────────────────
    if not issues:
        issues.append("✅ Car balance nominal across all three sectors")
        recs.append("Minor setup refinements only — focus on driver feedback on brake bias")

    # ── Circuit DNA note ─────────────────────────────────────────────────
    dna_line = f"\n📌 <b>Circuit characteristic:</b> {circuit_note}" if circuit_note else ""

    # ── Build report ─────────────────────────────────────────────────────
    report = "📊 <b>Engineering Report — Practice Session</b>\n\n"
    report += "<b>Issues Found:</b>\n" + "\n".join(f"  {i}" for i in issues)
    report += "\n\n<b>Recommendations:</b>\n" + "\n".join(f"  • {r}" for r in recs)
    if weather_section:
        report += f"\n\n{weather_section}"
    if dna_line:
        report += dna_line

    # ── Staff pre-race inputs ─────────────────────────────────────────────
    if staff_list:
        staff_section = generate_staff_practice_inputs(
            staff_list, car, weather, race_name, circuit_name, dna
        )
        if staff_section:
            report += f"\n\n{staff_section}"

    return report


# ─────────────────────────────────────────────────────────────────────────────
# STAFF PRE-RACE / PRACTICE INPUTS
# Each hired role gives circuit+condition-specific advice before qualifying
# ─────────────────────────────────────────────────────────────────────────────

STAFF_PRACTICE_TEMPLATES = {
    "technical_director": [
        "🔬 <b>{name} (Technical Director):</b>\n"
        "Looking at the {circuit} data — our {best_stat} is a real advantage here. "
        "{circuit_td_note} I want to trial {td_upgrade} before qualifying.",

        "🔬 <b>{name} (Technical Director):</b>\n"
        "{circuit_td_note} Our {worst_stat} is the concern for this weekend. "
        "I'm authorising a setup change to {td_fix} — should recover {td_gain}.",
    ],
    "chief_designer": [
        "📐 <b>{name} (Chief Designer):</b>\n"
        "For {circuit_name}, I've spec'd a {wing_config} setup. "
        "{balance_note}. The {chassis_note}.",

        "📐 <b>{name} (Chief Designer):</b>\n"
        "{circuit_name} is a {circuit_character} circuit — "
        "our philosophy suits it {suit_rating}. {designer_rec}.",
    ],
    "head_of_aerodynamics": [
        "💨 <b>{name} (Head of Aerodynamics):</b>\n"
        "CFD data for {circuit_name}: {aero_insight}. "
        "I recommend {aero_wing_rec} to maximise {aero_priority}.",

        "💨 <b>{name} (Head of Aerodynamics):</b>\n"
        "{circuit_name} requires {aero_demand}. "
        "Our current package gives {aero_current_rating} — {aero_action}.",
    ],
    "aerodynamicist": [
        "💨 <b>{name} (Aerodynamicist):</b>\n"
        "Tunnel simulation matched track data in sector {best_sector}. "
        "{aero_issue_small}. Will refine the {aero_part} overnight.",
    ],
    "race_engineer": [
        "📡 <b>{name} (Race Engineer):</b>\n"
        "Telemetry from FP1 shows {driver_name} is {driver_practice_note}. "
        "{re_setup_rec}. Target lap delta: -{re_gain}s.",

        "📡 <b>{name} (Race Engineer):</b>\n"
        "{driver_name} reported {driver_feel} through {circuit_section}. "
        "I'm adjusting {re_adjust} — should help in qualifying.",
    ],
    "chief_race_engineer": [
        "📻 <b>{name} (Chief Race Engineer):</b>\n"
        "Modelled {models_run} strategies for {circuit_name}. "
        "Primary plan: {strategy_plan}. "
        "{weather_strategy_note}. SC probability: {sc_prob}%.",

        "📻 <b>{name} (Chief Race Engineer):</b>\n"
        "For {circuit_name} — {strategy_headline}. "
        "{pit_window_note}. Tyre order recommendation: {tyre_order}.",
    ],
    "head_of_strategy": [
        "📊 <b>{name} (Head of Strategy):</b>\n"
        "Ran {models_run} race simulations overnight. "
        "Optimal strategy for {circuit_name}: {strategy_plan}. "
        "Key decision point: lap {decision_lap}. {undercut_note}.",

        "📊 <b>{name} (Head of Strategy):</b>\n"
        "{circuit_name} historically has SC probability of {sc_prob}%. "
        "I recommend {sc_plan}. {weather_strategy_note}.",
    ],
    "pit_crew_chief": [
        "🔧 <b>{name} (Pit Crew Chief):</b>\n"
        "Pit lane analysis for {circuit_name}: {pit_lane_note}. "
        "Crew drilled {drill_focus} this morning — targeting {target_stop}s stops.",

        "🔧 <b>{name} (Pit Crew Chief):</b>\n"
        "Pit entry/exit delta at {circuit_name} is {pit_delta}s. "
        "{pit_strategy_note}. We're ready for {expected_stops} stops.",
    ],
    "sporting_director": [
        "📋 <b>{name} (Sporting Director):</b>\n"
        "Tyre allocation for {circuit_name}: {tyre_alloc}. "
        "{regulation_note}. Pre-race parc fermé briefing at T-4h.",

        "📋 <b>{name} (Sporting Director):</b>\n"
        "Rival teams running {rival_note} at {circuit_name}. "
        "{sporting_rec}. {regulation_note}.",
    ],
    "power_unit_director": [
        "⚡ <b>{name} (Power Unit Director):</b>\n"
        "{circuit_name} is {pu_circuit_demand}. "
        "Setting engine to {pu_mode_rec} for qualifying; {pu_race_mode} for race. "
        "ERS deployment: {ers_plan}.",

        "⚡ <b>{name} (Power Unit Director):</b>\n"
        "Thermal data from FP shows {thermal_status}. "
        "{pu_action}. {token_status}.",
    ],
    "team_principal": [
        "🎙️ <b>{name} (Team Principal):</b>\n"
        "{circuit_name} is a {tp_circuit_feel} race for us. "
        "Target: {tp_target}. {tp_motivation}.",
    ],
    "performance_director": [
        "📈 <b>{name} (Performance Director):</b>\n"
        "Performance index coming into {circuit_name}: {perf_index}/100. "
        "Key metric to improve: {worst_stat}. {perf_action}.",
    ],
}


def generate_staff_practice_inputs(
    staff_list: list,
    car: CarEntry,
    weather: Weather,
    race_name: str,
    circuit_name: str,
    dna: dict,
) -> str:
    """Generate pre-race/practice staff inputs — circuit and condition aware."""
    import random

    if not staff_list:
        return ""

    tyre_stress   = dna.get("tyre_stress", 1.0)
    engine_mod    = dna.get("engine_mod", 1.0)
    overtaking_mod = dna.get("overtaking_mod", 1.0)
    weather_volatile = dna.get("weather_volatile", False)
    weather_str = weather.value.replace("_", " ")

    team_stats = {
        "engine": car.engine, "aerodynamics": car.aerodynamics,
        "chassis": car.chassis, "reliability": car.reliability,
        "tyres": car.tyre_mgmt, "pit_crew": car.pit_crew,
    }
    stat_labels = {
        "engine": "power unit", "aerodynamics": "aero package",
        "chassis": "chassis", "reliability": "reliability",
        "tyres": "tyre management", "pit_crew": "pit crew",
    }
    best_stat_key  = max(team_stats, key=team_stats.get)
    worst_stat_key = min(team_stats, key=team_stats.get)

    # Circuit character strings
    if overtaking_mod <= 0.4:
        circuit_character = "street/low-overtaking"
        aero_demand = "maximum downforce"
        aero_wing_rec = "high rear wing + maximum front flap"
        aero_priority = "mechanical grip in slow corners"
        wing_config = "high-downforce"
        circuit_section = "the tight hairpins"
    elif engine_mod >= 1.2:
        circuit_character = "high-speed power"
        aero_demand = "minimum drag"
        aero_wing_rec = "low rear wing, slim front flap"
        aero_priority = "straight-line speed"
        wing_config = "low-drag"
        circuit_section = "the long straights"
    elif weather_volatile or weather in [Weather.LIGHT_RAIN, Weather.HEAVY_RAIN, Weather.MIXED]:
        circuit_character = "weather-volatile"
        aero_demand = "balanced downforce with wet-weather robustness"
        aero_wing_rec = "medium wing angles for wet/dry flexibility"
        aero_priority = "aero stability in mixed conditions"
        wing_config = "balanced"
        circuit_section = "the mixed-condition corners"
    else:
        circuit_character = "technical balanced"
        aero_demand = "balanced downforce and drag"
        aero_wing_rec = "neutral wing angles, slight front bias"
        aero_priority = "overall aero balance"
        wing_config = "balanced"
        circuit_section = "the technical sector 2"

    # Tyre strategy options by circuit
    if tyre_stress >= 1.2:
        strategy_plan = "2-stop: Soft→Medium→Hard — tyres will struggle at this circuit"
        tyre_order = "Soft→Medium→Hard"
    elif tyre_stress <= 0.85:
        strategy_plan = "1-stop: Medium→Hard — low degradation circuit"
        tyre_order = "Medium→Hard"
    else:
        strategy_plan = "1-stop Medium→Hard or aggressive 2-stop Soft→Soft→Medium"
        tyre_order = "Medium→Hard (primary), Soft start (alternative)"

    decision_lap = random.randint(18, 32)
    sc_prob = random.randint(10, 50) + (15 if weather_volatile else 0)
    sc_plan = "keep an extra soft set ready for SC restart" if sc_prob > 35 else "standard plan — SC unlikely"

    weather_strategy_note = (
        f"In {weather_str}, intermediates may open a free stop window"
        if weather in [Weather.LIGHT_RAIN, Weather.MIXED]
        else ("Full wet start — switch to inters lap 3–5 if rain eases"
              if weather == Weather.HEAVY_RAIN
              else "Dry race expected — no weather wildcard")
    )

    # Circuit-specific TD notes
    if engine_mod >= 1.2:
        circuit_td_note = f"This is a power circuit (engine_mod {engine_mod:.2f}x) — our PU performance will be decisive."
        td_upgrade = "reduced-drag front wing specification"
        td_fix = "optimise ERS deployment on the long straights"
        td_gain = "0.2–0.3s per lap"
    elif overtaking_mod <= 0.5:
        circuit_td_note = "Qualifying position is everything here — setup must be pure low-speed grip."
        td_upgrade = "extra front wing Gurney flap"
        td_fix = "maximise mechanical grip in slow corners"
        td_gain = "improved consistency through S2"
    elif tyre_stress >= 1.1:
        circuit_td_note = f"Tyre stress is high ({tyre_stress:.1f}x) — management will be the race differentiator."
        td_upgrade = "revised brake cooling ducts to protect rear tyres"
        td_fix = "softer rear compounds to reduce inner edge wear"
        td_gain = "extra 3–4 laps on each stint"
    else:
        circuit_td_note = f"Balanced circuit — our {stat_labels[best_stat_key]} should shine."
        td_upgrade = "revised floor edge geometry"
        td_fix = "balance the car more neutrally through all corner speeds"
        td_gain = "0.15s"

    # Balance / chassis notes
    if car.chassis >= 70:
        balance_note = "Car feels planted — minor ARB adjustment only"
        chassis_note = "chassis is providing excellent platform for all corner types"
    else:
        balance_note = "We have understeer in S2 — need to redistribute balance forward"
        chassis_note = "chassis needs stiffer front spring to help rotation"

    # Suit rating
    if (circuit_character == "high-speed power" and car.engine >= 70) or \
       (circuit_character == "street/low-overtaking" and car.aerodynamics >= 70) or \
       (circuit_character == "technical balanced" and car.chassis >= 65):
        suit_rating = "very well"
        designer_rec = f"Stick with current setup philosophy — no major changes"
    else:
        suit_rating = "partially"
        designer_rec = f"I want to trial a revised {wing_config} wing package before qualifying"

    # Aero insights
    aero_insight = (
        f"drag coefficient {'optimal' if car.aerodynamics >= 65 else 'above target'} for {circuit_character} demands"
    )
    aero_current_rating = "competitive" if car.aerodynamics >= 65 else "below target"
    aero_action = (
        "no change needed — confident in the package"
        if car.aerodynamics >= 65
        else f"I want to run a revised {aero_wing_rec} in FP2"
    )
    aero_issue_small = (
        "Minor separation at rear beam wing above 270km/h" if car.aerodynamics < 65
        else "Clean aero data — no anomalies detected"
    )
    aero_part = "rear diffuser" if car.aerodynamics < 65 else "front wing endplates"
    best_sector = random.choice([1, 2, 3])

    # RE notes
    driver_practice_note = (
        "finding the limit well — just needs tyre warm-up routine"
        if car.chassis >= 65 else
        "struggling with understeer on entry — setup change needed"
    )
    re_setup_rec = (
        "Adjusting brake bias 1 click forward and softening front ARB"
        if car.chassis < 65 else
        "Setup is working — just refining brake bias for race start"
    )
    re_gain = round(random.uniform(0.1, 0.4), 2)
    driver_feel = (
        "good balance through the fast stuff" if car.chassis >= 65
        else "rear instability under braking"
    )
    re_adjust = "rear damper rebound settings" if car.chassis < 65 else "front spring rate"

    # PU director
    if engine_mod >= 1.15:
        pu_circuit_demand = f"a power-critical circuit (mod {engine_mod:.2f}x)"
        pu_mode_rec = "QUAL mode for maximum power"
        pu_race_mode = "FLOW mode to protect the unit"
        ers_plan = "full deployment on S1 and S3 straights; harvest through S2"
    else:
        pu_circuit_demand = "moderately power-sensitive"
        pu_mode_rec = "standard QUAL mode"
        pu_race_mode = "standard RACE mode"
        ers_plan = "balanced deployment throughout"
    thermal_status = (
        "all temps in green — PU comfortable" if car.reliability >= 65
        else "yellow on MGU-H temperatures — monitoring closely"
    )
    pu_action = (
        "No action needed — PU in excellent health" if car.reliability >= 65
        else "Running cooling mode in S2 until temperatures normalise"
    )
    token_status = random.choice([
        "1 development token remaining this season",
        "2 tokens left — may deploy one here if data supports it",
        "Token freeze in effect — no PU changes permitted",
    ])

    # Pit crew
    pit_lane_note = (
        "Pit lane entry is tight here — coordinate brake regen carefully"
        if circuit_character == "street/low-overtaking"
        else "Clean pit lane entry — standard procedure"
    )
    drill_focus = random.choice(["front jack speed", "rear wheel gun timing", "tyre heating protocol", "lollipop release"])
    target_stop = round(random.uniform(2.2, 3.0), 1)
    pit_delta = round(random.uniform(17, 24), 1)
    pit_strategy_note = (
        "Undercut is powerful here — aim to pit 2 laps earlier than rivals"
        if overtaking_mod <= 0.6
        else "Overcut viable — tyre delta will be the deciding factor"
    )
    expected_stops = "2" if tyre_stress >= 1.1 else "1"

    # Sporting director
    tyre_alloc = random.choice([
        "3 Soft / 3 Medium / 2 Hard",
        "2 Soft / 4 Medium / 2 Hard",
        "4 Soft / 2 Medium / 2 Hard",
    ])
    regulation_note = random.choice([
        "Parc fermé applies post-qualifying — no setup changes permitted",
        "DRS detection point confirmed — check it in FP2",
        "Front wing flexibility test scheduled post-FP2",
    ])
    rival_note = random.choice([
        "high-downforce configs",
        "low-drag setups",
        "mixed strategies — hard to read",
    ])
    sporting_rec = (
        "Suggest we box earliest to avoid traffic — pit lane is short here"
        if circuit_character == "street/low-overtaking"
        else "Standard tyre allocation strategy — no surprises expected"
    )

    # TP
    tp_circuit_feel = (
        "historically strong" if car.engine >= 65 and car.aerodynamics >= 65
        else "challenging but an opportunity"
    )
    tp_target = (
        f"Top 5 minimum" if car.engine >= 70
        else "Points finish and strong learning weekend"
    )
    tp_motivation = random.choice([
        "The team is ready — let's execute perfectly.",
        "I believe in this car and this team — let's show it.",
        "Rivals won't see us coming — stay focused.",
    ])

    # Perf director
    perf_index = min(99, max(40, int((car.engine + car.aerodynamics + car.chassis) / 3) + random.randint(-5, 5)))
    perf_action = (
        f"If we improve {stat_labels[worst_stat_key]} by 10 points, we estimate a P{random.randint(1,3)} gain on grid."
    )

    ctx = {
        "name": "",
        "circuit_name": circuit_name or race_name,
        "circuit_character": circuit_character,
        "circuit_section": circuit_section,
        "circuit_td_note": circuit_td_note,
        "best_stat": stat_labels[best_stat_key],
        "worst_stat": stat_labels[worst_stat_key],
        "td_upgrade": td_upgrade,
        "td_fix": td_fix,
        "td_gain": td_gain,
        "wing_config": wing_config,
        "balance_note": balance_note,
        "chassis_note": chassis_note,
        "suit_rating": suit_rating,
        "designer_rec": designer_rec,
        "aero_insight": aero_insight,
        "aero_current_rating": aero_current_rating,
        "aero_action": aero_action,
        "aero_demand": aero_demand,
        "aero_wing_rec": aero_wing_rec,
        "aero_priority": aero_priority,
        "aero_issue_small": aero_issue_small,
        "aero_part": aero_part,
        "best_sector": best_sector,
        "driver_name": car.driver_name,
        "driver_practice_note": driver_practice_note,
        "re_setup_rec": re_setup_rec,
        "re_gain": re_gain,
        "driver_feel": driver_feel,
        "re_adjust": re_adjust,
        "models_run": random.randint(12, 40),
        "strategy_plan": strategy_plan,
        "weather_strategy_note": weather_strategy_note,
        "sc_prob": sc_prob,
        "sc_plan": sc_plan,
        "decision_lap": decision_lap,
        "strategy_headline": strategy_plan,
        "pit_window_note": f"Pit window: lap {decision_lap}–{decision_lap + 4}",
        "tyre_order": tyre_order,
        "pit_lane_note": pit_lane_note,
        "drill_focus": drill_focus,
        "target_stop": target_stop,
        "pit_delta": pit_delta,
        "pit_strategy_note": pit_strategy_note,
        "expected_stops": expected_stops,
        "tyre_alloc": tyre_alloc,
        "regulation_note": regulation_note,
        "rival_note": rival_note,
        "sporting_rec": sporting_rec,
        "pu_circuit_demand": pu_circuit_demand,
        "pu_mode_rec": pu_mode_rec,
        "pu_race_mode": pu_race_mode,
        "ers_plan": ers_plan,
        "thermal_status": thermal_status,
        "pu_action": pu_action,
        "token_status": token_status,
        "tp_circuit_feel": tp_circuit_feel,
        "tp_target": tp_target,
        "tp_motivation": tp_motivation,
        "perf_index": perf_index,
        "perf_action": perf_action,
    }

    lines = [f"\n👥 <b>PRE-RACE STAFF BRIEFING — {(circuit_name or race_name).upper()}</b>\n"]

    seen_roles = set()
    for _, s in staff_list:
        role = s.role.value if hasattr(s.role, "value") else str(s.role)
        if role in seen_roles:
            continue
        seen_roles.add(role)

        templates = STAFF_PRACTICE_TEMPLATES.get(role, [])
        if not templates:
            continue

        template = random.choice(templates)
        ctx["name"] = s.name
        try:
            lines.append(template.format(**ctx))
            lines.append("")
        except KeyError:
            lines.append(f"🗣️ <b>{s.name}:</b> Preparing setup recommendations for {circuit_name or race_name}.")
            lines.append("")

    if len(lines) <= 1:
        return ""

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# STAFF POST-RACE INSIGHTS
# Each role gives different, dynamic commentary based on actual race data
# ─────────────────────────────────────────────────────────────────────────────

ROLE_INSIGHT_TEMPLATES = {
    "team_principal": [
        "🎙️ <b>{name} (Team Principal):</b>\n"
        "P{position} today — {result_comment}. {budget_comment}. "
        "We {points_comment}. Next race at {next_circuit}, we need to {tp_action}.",

        "🎙️ <b>{name} (Team Principal):</b>\n"
        "{mood} after {circuit}. {weather_comment}. "
        "The whole team {team_comment}. {season_comment}.",
    ],
    "technical_director": [
        "🔬 <b>{name} (Technical Director):</b>\n"
        "Car performance analysis — {car_rating}. "
        "{aero_comment}. {engine_comment}. "
        "Biggest concern: {concern}. Next upgrade target: {upgrade_target}.",

        "🔬 <b>{name} (Technical Director):</b>\n"
        "Our {best_stat} is clearly our {best_comment}. "
        "{weakness_comment}. "
        "I'm pushing the factory to {factory_target} before {next_circuit}.",
    ],
    "chief_designer": [
        "📐 <b>{name} (Chief Designer):</b>\n"
        "The car {car_balance} in {weather_str} conditions today. "
        "{setup_comment}. For {next_circuit}, I recommend {setup_recommendation}.",
    ],
    "head_of_aerodynamics": [
        "💨 <b>{name} (Head of Aerodynamics):</b>\n"
        "Aero data from {circuit}: {aero_analysis}. "
        "Downforce efficiency was {downforce_rating}. "
        "{drag_comment}. I want to trial {aero_next} at {next_circuit}.",
    ],
    "aerodynamicist": [
        "💨 <b>{name} (Aerodynamicist):</b>\n"
        "CFD correlated well in sector {best_sector} today. "
        "{aero_issue}. Will refine the {aero_part} package overnight.",
    ],
    "chief_race_engineer": [
        "📻 <b>{name} (Chief Race Engineer):</b>\n"
        "Strategy call analysis — {strategy_verdict}. "
        "{pit_comment}. Driver feedback: {driver_feedback}. "
        "{weather_strategy_comment}.",

        "📻 <b>{name} (Chief Race Engineer):</b>\n"
        "{pit_timing_comment}. {undercut_comment}. "
        "Tyre degradation was {deg_comment} than expected. "
        "For {next_circuit}: {next_strategy_hint}.",
    ],
    "race_engineer": [
        "📡 <b>{name} (Race Engineer):</b>\n"
        "On-track comms analysis: {driver_name} had {lap_comment}. "
        "{tyre_comment}. Setup changes for {next_circuit}: {setup_change}.",
    ],
    "pit_crew_chief": [
        "🔧 <b>{name} (Pit Crew Chief):</b>\n"
        "{stops} stop(s) executed. Best stop: {best_stop_time}s. "
        "{stop_comment}. The crew {crew_rating}. "
        "We'll drill {drill_focus} this week.",
    ],
    "sporting_director": [
        "📋 <b>{name} (Sporting Director):</b>\n"
        "Protest risk: {protest_comment}. "
        "Tyre allocation for {next_circuit}: {tyre_alloc}. "
        "{regulation_note}.",
    ],
    "power_unit_director": [
        "⚡ <b>{name} (Power Unit Director):</b>\n"
        "PU performance at {circuit}: {pu_comment}. "
        "Deployment mode: {pu_mode}. Thermal data: {thermal_comment}. "
        "Token usage: {token_comment}.",
    ],
    "head_of_strategy": [
        "📊 <b>{name} (Head of Strategy):</b>\n"
        "We modelled {models_run} scenarios pre-race. Chose {strategy_chosen} — {strategy_verdict}. "
        "{undercut_comment}. VSC/SC probability for {next_circuit}: {sc_prob}%. "
        "Recommend {next_strategy_hint}.",
    ],
    "performance_director": [
        "📈 <b>{name} (Performance Director):</b>\n"
        "Overall performance index: {perf_score}/100. "
        "{strongest_area} is our biggest strength, {weakest_area} needs work. "
        "{benchmark_comment}. Target for next race: P{target_position}.",
    ],
}


def _result_comment(position: int) -> str:
    if position == 1: return "an absolutely dominant victory"
    if position <= 3: return "a solid podium finish"
    if position <= 5: return "points but we wanted more"
    if position <= 10: return "a points finish — acceptable"
    return "a difficult afternoon we need to learn from"

def _mood(position: int) -> str:
    if position == 1: return "Ecstatic"
    if position <= 3: return "Very pleased"
    if position <= 6: return "Reasonably satisfied"
    if position <= 10: return "Mixed feelings"
    return "Deeply frustrated"

def _car_rating(engine, aero, chassis) -> str:
    avg = (engine + aero + chassis) / 3
    if avg >= 85: return "exceptional across all metrics"
    if avg >= 70: return "strong in most areas"
    if avg >= 55: return "showing promise but gaps remain"
    return "clearly needing development investment"

def _best_stat_name(team_stats: dict) -> tuple:
    best = max(team_stats, key=team_stats.get)
    labels = {"engine": "power unit", "aerodynamics": "aero package",
               "chassis": "chassis", "reliability": "reliability",
               "tyres": "tyre management", "pit_crew": "pit crew"}
    return best, labels.get(best, best)

def _worst_stat_name(team_stats: dict) -> tuple:
    worst = min(team_stats, key=team_stats.get)
    labels = {"engine": "power unit", "aerodynamics": "aero package",
               "chassis": "chassis", "reliability": "reliability",
               "tyres": "tyre management", "pit_crew": "pit crew"}
    return worst, labels.get(worst, worst)


def generate_staff_race_insights(
    staff_list: list,           # list of (TeamStaff, Staff) tuples
    race_result: dict,          # full result dict from simulate_race
    team_id: int,
    team_stats: dict,           # {"engine": x, "aerodynamics": x, ...}
    next_circuit: str = "the next race",
) -> str:
    """
    Generate unique post-race insights from each hired staff member.
    Every race gives different commentary based on actual result data.
    """
    if not staff_list:
        return "⚠️ No staff hired — hire staff to receive expert race insights!"

    # Extract team's car result
    team_cars = [c for c in race_result["results"] if c.team_id == team_id]
    if not team_cars:
        return "No race data available for your team."

    best_car = min(team_cars, key=lambda c: c.position if not c.is_dnf else 999)
    position = best_car.position if not best_car.is_dnf else 20
    dnf = best_car.is_dnf
    pit_stops = best_car.pit_stops_done
    strategy = best_car.strategy
    weather = race_result["weather"]
    circuit = race_result["circuit"]
    weather_str = weather.value.replace("_", " ")
    total_cars = len(race_result["results"])
    points_earned = max(0, [25,18,15,12,10,8,6,4,2,1,0,0,0,0,0,0,0,0,0,0][position-1] if position <= 20 else 0)

    best_stat_key, best_stat_label = _best_stat_name(team_stats)
    worst_stat_key, worst_stat_label = _worst_stat_name(team_stats)

    # Dynamic values based on race data
    ctx = {
        "position": position,
        "circuit": circuit,
        "next_circuit": next_circuit,
        "weather_str": weather_str,
        "strategy_chosen": strategy,
        "stops": pit_stops,
        "driver_name": best_car.driver_name,
        "result_comment": _result_comment(position),
        "mood": _mood(position),
        "car_rating": _car_rating(team_stats.get("engine",50), team_stats.get("aerodynamics",50), team_stats.get("chassis",50)),
        "best_stat": best_stat_key,
        "best_comment": best_stat_label + (" is a real weapon" if team_stats.get(best_stat_key,50) >= 75 else " is competitive"),
        "weakness_comment": f"But our {worst_stat_label} at {team_stats.get(worst_stat_key,50)}/100 is holding us back",
        "weakest_area": worst_stat_label,
        "strongest_area": best_stat_label,
        "aero_comment": "Downforce levels were well-matched to this circuit" if team_stats.get("aerodynamics",50) >= 65 else "We were losing time in the high-speed sections — aero deficit clear",
        "engine_comment": "Power unit felt strong on the straights" if team_stats.get("engine",50) >= 65 else "Top speed delta to leaders is a concern",
        "concern": worst_stat_label + " performance",
        "upgrade_target": best_stat_label + " refinement" if position <= 5 else worst_stat_label + " improvement",
        "factory_target": "complete the floor upgrade" if team_stats.get("aerodynamics",50) < 70 else "finalise the new suspension geometry",
        "car_balance": "felt planted and balanced" if not dnf else "suffered a terminal failure — frustrating",
        "setup_comment": "Wing angles were optimal for traction zones" if team_stats.get("chassis",50) >= 65 else "We had too much understeer in slow-speed sections",
        "setup_recommendation": "softer rear suspension to help rotation" if team_stats.get("chassis",50) < 65 else "a more aggressive front wing for extra downforce",
        "aero_analysis": f"drag was {'acceptable' if team_stats.get('aerodynamics',50) >= 65 else 'too high'}, downforce balance was {'good' if team_stats.get('aerodynamics',50) >= 70 else 'lacking'}",
        "downforce_rating": "competitive" if team_stats.get("aerodynamics",50) >= 65 else "below target",
        "drag_comment": "Straight-line speed was good" if team_stats.get("engine",50) >= 65 else "We gave up too much on the straights",
        "aero_next": "a new front wing spec" if team_stats.get("aerodynamics",50) < 70 else "a revised diffuser package",
        "aero_issue": "Separated flow on the rear wing above 280km/h detected" if team_stats.get("aerodynamics",50) < 70 else "Clean aero data throughout — no anomalies",
        "aero_part": "rear diffuser" if team_stats.get("aerodynamics",50) < 70 else "front wing",
        "best_sector": random.choice([1, 2, 3]),
        "strategy_verdict": ("excellent call — exactly right for conditions" if position <= 4
                             else "reasonable but we could have been more aggressive" if position <= 8
                             else "we got caught out — need better real-time data"),
        "pit_comment": f"Pit window opened lap {'early' if pit_stops >= 2 else 'as planned'}",
        "driver_feedback": ("positive — car felt consistent all race" if team_stats.get("chassis",50) >= 65
                            else "reported heavy degradation in the final stint"),
        "weather_strategy_comment": (f"The {weather_str} conditions caught several rivals — we were prepared" if weather.value in ["light_rain","heavy_rain","mixed"]
                                     else "Dry conditions meant strategy was the main variable"),
        "pit_timing_comment": f"We {'nailed' if position <= 5 else 'slightly missed'} the undercut window",
        "undercut_comment": ("Undercut on lap " + str(random.randint(15,30)) + " was decisive" if position <= 5
                              else "We responded too slowly to the overcut threat"),
        "deg_comment": random.choice(["better", "worse", "exactly as expected"]),
        "next_strategy_hint": ("2-stop aggressive — tyres should suit us" if team_stats.get("tyres",50) < 65
                               else "1-stop with softs at the end — we have the tyre life"),
        "lap_comment": ("consistently fast laps throughout" if team_stats.get("chassis",50) >= 65
                        else "struggled with oversteer in sector 2 — we'll fix that"),
        "tyre_comment": ("Tyre management was impressive — lasted longer than expected" if team_stats.get("tyres",50) >= 65
                         else "Tyre degradation was a real problem — need to address setup"),
        "setup_change": ("lower rear wing, stiffer front suspension" if team_stats.get("aerodynamics",50) >= 65
                         else "higher front wing angle, softer rear springs"),
        "best_stop_time": f"{random.uniform(2.3, 3.2):.1f}",
        "stop_comment": ("All stops clean — great execution" if team_stats.get("pit_crew",50) >= 70
                         else "One slow stop cost us position — drilled that this week"),
        "crew_rating": ("executed perfectly under pressure" if team_stats.get("pit_crew",50) >= 70
                        else "need to be sharper — a tenth lost in the pits today"),
        "drill_focus": random.choice(["wheel gun speed", "front jack timing", "tyre heating protocol", "lollipop release timing"]),
        "protest_comment": random.choice(["Low — clean race from us", "One borderline move under investigation", "None — by the book today"]),
        "tyre_alloc": random.choice(["3 soft, 3 medium, 2 hard sets", "2 soft, 4 medium, 2 hard sets", "4 soft, 2 medium, 2 hard sets"]),
        "regulation_note": random.choice(["Parc fermé conditions checked — no issues", "Front wing within tolerance — confirmed post-race", "Floor measurements passed scrutineering"]),
        "pu_comment": ("Strong deployment throughout — ERS worked perfectly" if team_stats.get("engine",50) >= 70
                       else "PU was protecting itself — thermal margins too tight"),
        "pu_mode": random.choice(["Party mode in Q3 only", "FLOW mode for race conservation", "Attack mode last 10 laps"]),
        "thermal_comment": ("Within green limits all race" if team_stats.get("reliability",50) >= 65
                            else "Yellow sector 2 — monitoring closely"),
        "token_comment": random.choice(["2 tokens remaining this season", "1 token used — one left", "No tokens spent — saving for next circuit"]),
        "models_run": random.randint(12, 40),
        "sc_prob": random.randint(15, 55),
        "perf_score": min(99, max(40, 50 + (10 - position) * 4 + random.randint(-5, 5))),
        "target_position": max(1, position - random.randint(1, 3)),
        "benchmark_comment": ("We're closing the gap to the leaders" if position <= 8
                              else "Still significant work to do to match the frontrunners"),
        "budget_comment": (f"${points_earned * 100_000:,} prize money secured" if points_earned > 0 else "No prize money today"),
        "points_comment": (f"scored {points_earned} valuable points" if points_earned > 0 else "came away empty-handed on points"),
        "tp_action": random.choice(["push harder on development", "focus on strategy execution", "nail qualifying — pace is there", "get both drivers in the points"]),
        "team_comment": random.choice(["delivered a great effort", "needs to respond better to strategy calls", "showed real character today", "worked flawlessly as a unit"]),
        "season_comment": (f"We're P{random.randint(1,5)} in the constructors — keep pushing" if position <= 8
                           else f"Need a strong run of results to move up the table"),
        "weather_comment": (f"The {weather_str} threw a curveball but we handled it" if weather.value not in ["sunny","cloudy"]
                            else "Clean conditions — no excuses, pure performance"),
    }

    lines = [f"📣 <b>POST-RACE STAFF DEBRIEF — {circuit.upper()}</b>\n"]
    lines.append(f"🏁 Result: P{position} | {best_car.driver_name} | {'DNF ❌' if dnf else 'Finished ✅'}\n")

    seen_roles = set()
    for _, s in staff_list:
        role = s.role.value if hasattr(s.role, "value") else str(s.role)
        if role in seen_roles:
            continue
        seen_roles.add(role)

        templates = ROLE_INSIGHT_TEMPLATES.get(role, [])
        if not templates:
            continue

        template = random.choice(templates)
        ctx["name"] = s.name

        try:
            insight = template.format(**ctx)
        except KeyError:
            insight = f"🗣️ <b>{s.name}:</b> Solid effort today — more analysis needed."

        lines.append(insight)
        lines.append("")

    return "\n".join(lines)
