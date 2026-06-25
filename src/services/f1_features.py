"""
F1 Extra Features
-----------------
1. Driver Morale & Happiness     — top driver in slow car gets unhappy
2. Team Radio Messages           — iconic radio moments during race
3. Post-race Press Conference    — player answers journalist question
4. Sprint Race Weekend           — mini race before main GP
"""
import random
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. DRIVER MORALE
# ─────────────────────────────────────────────────────────────────────────────

# How many positions "below potential" triggers unhappiness
MORALE_THRESHOLD = 6   # if driver skill > 88 and team finishes P7+ below → unhappy

MORALE_MESSAGES = {
    "very_unhappy": [
        "🔴 {driver} is seriously unhappy. They've requested a transfer listing!",
        "🔴 {driver} told the press: 'I need a car that matches my ability.' Transfer imminent!",
    ],
    "unhappy": [
        "🟡 {driver} seems frustrated. A pay rise or better car results would help morale.",
        "🟡 {driver}: 'The car isn't giving me what I need right now.' Morale dropping.",
    ],
    "happy": [
        "🟢 {driver} is in great spirits after a strong result!",
        "🟢 {driver}: 'The team is doing a fantastic job. I love it here.'",
    ],
}

def check_driver_morale(
    driver_name: str,
    driver_skill: int,
    finish_position: int,
    team_car_avg: int,   # avg of team's car stats
    races_done: int,
) -> dict:
    """
    Returns morale status and optional message.
    Called after each race for each driver.
    """
    # Star driver (85+) finishing badly in a weak car
    talent_wasted = driver_skill >= 85 and team_car_avg < 65 and finish_position > 8

    # Good result for the car level → happy
    expected_pos = max(1, int(20 * (1 - team_car_avg / 100)) + 1)
    overperformed = finish_position <= expected_pos - 3

    if talent_wasted and races_done >= 3:
        severity = "very_unhappy" if finish_position > 12 else "unhappy"
        msg = random.choice(MORALE_MESSAGES[severity]).format(driver=driver_name)
        return {"status": severity, "message": msg, "wants_transfer": severity == "very_unhappy"}

    if overperformed:
        msg = random.choice(MORALE_MESSAGES["happy"]).format(driver=driver_name)
        return {"status": "happy", "message": msg, "wants_transfer": False}

    return {"status": "neutral", "message": None, "wants_transfer": False}


# ─────────────────────────────────────────────────────────────────────────────
# 2. TEAM RADIO MESSAGES
# ─────────────────────────────────────────────────────────────────────────────

RADIO_TRIGGERS = {
    "pit_call": [
        "🎙️ Engineer: \"{driver}, box box box! We're bringing you in this lap!\"",
        "🎙️ Engineer: \"Copy, {driver} — pit this lap. Mediums ready. Box box box.\"",
        "🎙️ Engineer: \"Target lap time minus 0.3. Box this lap. Box box.\"",
    ],
    "fastest_lap": [
        "🎙️ Engineer: \"Fastest lap, {driver}! PURPLE SECTOR! Keep pushing!\"",
        "🎙️ Engineer: \"That's P1 on the timing sheet! Incredible lap, {driver}!\"",
        "🎙️ Engineer: \"Purple, purple, purple! You're the quickest car on track!\"",
    ],
    "safety_car": [
        "🎙️ Engineer: \"Safety car deployed, {driver}. We're monitoring the situation.\"",
        "🎙️ Engineer: \"SC out. Push push push to close the gap before it comes in.\"",
        "🎙️ Engineer: \"Safety car in this lap. Be ready for the restart. Tyres in window.\"",
    ],
    "overtake": [
        "🎙️ Engineer: \"Car ahead is struggling — DRS available. Attack on turn 1!\"",
        "🎙️ Engineer: \"Gap is 0.8 and closing. You've got better pace. Hunt him down.\"",
        "🎙️ Engineer: \"He's vulnerable under braking. Go for it on the next lap!\"",
    ],
    "dnf": [
        "🎙️ Engineer: \"We have to retire the car. I'm sorry, {driver}. Park it safely.\"",
        "🎙️ Engineer: \"{driver}, we have a critical failure. Bring it home slowly if you can. Stop the car.\"",
        "🎙️ Engineer: \"Power unit issue. We're going to have to stop. Really sorry.\"",
    ],
    "podium": [
        "🎙️ Engineer: \"P{pos}! PODIUM! Incredible job {driver} — the team is going crazy!\"",
        "🎙️ Engineer: \"That's P{pos}, {driver}! You gave everything today! Brilliant drive!\"",
    ],
    "win": [
        "🎙️ Engineer: \"WINNER! {driver} YOU ARE THE RACE WINNER! GET IN THERE!\"",
        "🎙️ Engineer: \"P1! CHEQUERED FLAG! UNBELIEVABLE {driver}! THAT'S A WIN!\"",
    ],
}

def get_radio_message(trigger: str, driver: str = "Driver", pos: int = 1) -> str:
    """Return a radio message for a given race event trigger."""
    options = RADIO_TRIGGERS.get(trigger, [])
    if not options:
        return ""
    msg = random.choice(options)
    return msg.format(driver=driver, pos=pos)


# ─────────────────────────────────────────────────────────────────────────────
# 3. POST-RACE PRESS CONFERENCE
# ─────────────────────────────────────────────────────────────────────────────

PRESS_QUESTIONS = [
    {
        "id": "q_pace",
        "question": "🎤 Journalist: \"Your pace in the middle stint was impressive. What was the key?\"",
        "options": {
            "aggressive":  ("'We took risks on strategy and it paid off.' [+2 Rep, rivals annoyed]",  2,  0),
            "diplomatic":  ("'Credit to the whole team — everyone played their part.' [+1 Rep]",       1,  0),
            "evasive":     ("'I can't reveal our strategy details.' [No change]",                      0,  0),
        },
    },
    {
        "id": "q_battle",
        "question": "🎤 Journalist: \"That battle in lap 34 — was it fair racing?\"",
        "options": {
            "aggressive":  ("'He left me no room. I'll race hard every time.' [-1 Rep with rivals]",   0, -1),
            "diplomatic":  ("'Hard but fair — that's what F1 is about.' [+1 Rep]",                    1,  0),
            "evasive":     ("'The stewards reviewed it and no further action was taken.' [No change]", 0,  0),
        },
    },
    {
        "id": "q_championship",
        "question": "🎤 Journalist: \"Are you thinking about the championship fight yet?\"",
        "options": {
            "aggressive":  ("'We're going for it — every point counts now.' [+2 Rep]",                2,  0),
            "diplomatic":  ("'We take it race by race and see where we end up.' [+1 Rep]",            1,  0),
            "evasive":     ("'It's too early to say anything concrete.' [No change]",                  0,  0),
        },
    },
    {
        "id": "q_car",
        "question": "🎤 Journalist: \"Are you happy with the car development direction?\"",
        "options": {
            "aggressive":  ("'We need to push harder in aero. Factory must step up.' [-1 Rep internally]", 0, -1),
            "diplomatic":  ("'The team is working incredibly hard and it shows.' [+1 Rep]",                1,  0),
            "evasive":     ("'There's always room for improvement — we're working on it.' [No change]",    0,  0),
        },
    },
]

def get_press_conference_question() -> dict:
    """Pick a random press conference question."""
    return random.choice(PRESS_QUESTIONS)

def apply_press_answer(answer_type: str, question: dict) -> tuple[int, int, str]:
    """
    Process player's press answer.
    Returns (reputation_change, rival_relation_change, response_text)
    """
    options = question.get("options", {})
    data = options.get(answer_type)
    if not data:
        return 0, 0, "No comment."
    text, rep_change, rival_change = data
    return rep_change, rival_change, text


# ─────────────────────────────────────────────────────────────────────────────
# 4. SPRINT RACE SIMULATION
# ─────────────────────────────────────────────────────────────────────────────

# Sprint points: 8-7-6-5-4-3-2-1 for P1-P8
SPRINT_POINTS = {1: 8, 2: 7, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}

SPRINT_LAPS = 17   # ~100km, roughly 17 laps average

# Sprint shootout lap multiplier (shorter than Q)
SPRINT_SHOOTOUT_LAP_MULT = 1.02


def simulate_sprint_race(entries: list, race_name: str = "") -> dict:
    """
    Run a sprint race (17 laps, reduced DNF chance, no pit stops).
    entries: same CarEntry list as main race.
    Returns dict with results, events, points.
    """
    from src.simulation.race_engine import (
        generate_weather, Weather, calculate_base_laptime,
        WEATHER_LABELS, get_dnf_probability,
    )
    try:
        from src.core.config import CIRCUIT_DNA
        dna = CIRCUIT_DNA.get(race_name, {})
    except ImportError:
        dna = {}

    weather = generate_weather()
    events = []
    events.append(f"⚡ <b>SPRINT RACE — {race_name}</b> | {WEATHER_LABELS[weather]} | {SPRINT_LAPS} laps")
    events.append("🚦 Sprint race STARTED!")

    # Reset race state (don't touch tyre/setup from qualifying)
    for i, car in enumerate(entries):
        car.position = i + 1
        car.tyre_wear = 0.0
        car.tyre_age = 0
        car.pit_stops_done = 0
        car.is_dnf = False
        car.total_time = 0.0
        car.gap_to_leader = 0.0
        # Sprint tyre — everyone starts on medium
        car.current_tyre = "medium"

    active = list(entries)
    dnf_cars = []

    for lap in range(1, SPRINT_LAPS + 1):
        for car in active[:]:
            # DNF chance halved in sprint
            dnf_prob = get_dnf_probability(car, lap, SPRINT_LAPS) * 0.5
            if random.random() < dnf_prob:
                car.is_dnf = True
                car.dnf_reason = random.choice(["Engine issue", "Hydraulics", "Collision", "Suspension"])
                events.append(f"💥 DNF: {car.driver_name} ({car.team_name}) — {car.dnf_reason}")
                active.remove(car)
                dnf_cars.append(car)
                continue

            lap_time = calculate_base_laptime(car, weather, dna)
            car.total_time += lap_time
            car.tyre_age += 1
            car.tyre_wear += 0.02  # slower wear (no push on sprint softs)

        # Sort active by total_time
        active.sort(key=lambda c: c.total_time)
        for i, car in enumerate(active):
            car.position = i + 1
            car.gap_to_leader = car.total_time - active[0].total_time

        # Lap events
        if lap == 1:
            if active:
                events.append(f"Lap 1 leader: <b>{active[0].driver_name}</b>")
        elif lap == SPRINT_LAPS // 2:
            if active:
                events.append(f"Halfway: <b>{active[0].driver_name}</b> leads | P2 {active[1].driver_name if len(active) > 1 else '—'} +{active[1].gap_to_leader:.2f}s" if len(active) > 1 else f"Halfway: <b>{active[0].driver_name}</b> leads")

    # Final order
    final_order = active + dnf_cars
    for i, car in enumerate(final_order):
        if not car.is_dnf:
            car.position = i + 1

    # Points
    sprint_results = []
    for car in final_order:
        pts = SPRINT_POINTS.get(car.position, 0) if not car.is_dnf else 0
        sprint_results.append({
            "position": car.position if not car.is_dnf else None,
            "driver":   car.driver_name,
            "team":     car.team_name,
            "team_id":  car.team_id,
            "driver_id": car.driver_id,
            "points":   pts,
            "dnf":      car.is_dnf,
            "fastest_lap": False,
        })

    # Winner message
    if final_order and not final_order[0].is_dnf:
        events.append(f"\n🏆 Sprint winner: <b>{final_order[0].driver_name}</b> ({final_order[0].team_name})")
        if len(final_order) > 1 and not final_order[1].is_dnf:
            events.append(f"🥈 P2: {final_order[1].driver_name} +{final_order[1].gap_to_leader:.3f}s")
        if len(final_order) > 2 and not final_order[2].is_dnf:
            events.append(f"🥉 P3: {final_order[2].driver_name} +{final_order[2].gap_to_leader:.3f}s")

    return {
        "type": "sprint",
        "race_name": race_name,
        "weather": weather,
        "results": sprint_results,
        "events": events,
        "sprint_points": SPRINT_POINTS,
    }
