"""
Stats & Social Handlers
/profile  — Player career stats + trophies
/halloffame — All-time champions
/h2h <@user> — Head to head record
"""
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from src.core.database.session import get_session
from src.services.game_services import TeamService, StandingsService
from sqlalchemy import select, and_, func
from src.models.models import (
    User, Team, RaceResult, TeamAchievement, Achievement,
    DriverStanding, ConstructorStanding, League, Race, RaceStatus,
    TeamDriver, Driver, Season
)

logger = logging.getLogger(__name__)
router = Router()


def safe(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ─────────────────────────────────────────────
# /profile
# ─────────────────────────────────────────────

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ You don't have a team yet. Use /register to create one.")
            return

        # Race results summary
        results_res = await db.execute(
            select(RaceResult).where(RaceResult.team_id == team.id)
        )
        results = results_res.scalars().all()

        total_races = len([r for r in results if not r.dnf])
        total_wins = len([r for r in results if r.position == 1])
        total_podiums = len([r for r in results if r.position and r.position <= 3])
        total_poles = team.poles
        total_points = team.total_points or 0
        total_dnf = len([r for r in results if r.dnf])
        fastest_laps = len([r for r in results if r.fastest_lap])
        win_rate = (total_wins / total_races * 100) if total_races > 0 else 0

        # Achievements
        ach_res = await db.execute(
            select(TeamAchievement, Achievement)
            .join(Achievement, TeamAchievement.achievement_key == Achievement.key)
            .where(TeamAchievement.team_id == team.id)
            .order_by(TeamAchievement.earned_at.desc())
        )
        achievements = ach_res.all()

        # Car rating (average of all stats)
        car_rating = (
            team.engine + team.aerodynamics + team.chassis +
            team.reliability + team.tyres + team.pit_crew
        ) // 6

        # Current drivers
        drivers_res = await db.execute(
            select(TeamDriver, Driver)
            .join(Driver, TeamDriver.driver_id == Driver.id)
            .where(TeamDriver.team_id == team.id)
        )
        drivers = drivers_res.all()

        # League & standing
        league_line = "Not in a league"
        if team.league_id:
            league_res = await db.execute(select(League).where(League.id == team.league_id))
            league = league_res.scalar_one_or_none()
            if league:
                standing_res = await db.execute(
                    select(ConstructorStanding)
                    .where(
                        and_(
                            ConstructorStanding.team_id == team.id,
                            ConstructorStanding.league_id == team.league_id,
                            ConstructorStanding.season == league.current_season,
                        )
                    )
                )
                standing = standing_res.scalar_one_or_none()
                pos = standing.position if standing and standing.position else "—"
                league_line = f"{safe(league.name)} — P{pos} (Season {league.current_season})"

        # Build message
        driver_lines = ""
        for td, d in drivers:
            avg_skill = (d.pace + d.racecraft + d.consistency) // 3
            driver_lines += f"  • {safe(d.name)} — Rating {avg_skill}/100\n"
        if not driver_lines:
            driver_lines = "  No drivers signed\n"

        ach_lines = ""
        for ta, a in achievements[:5]:
            ach_lines += f"  {a.icon} {safe(a.name)}\n"
        if not ach_lines:
            ach_lines = "  No achievements yet\n"
        if len(achievements) > 5:
            ach_lines += f"  <i>...and {len(achievements) - 5} more</i>\n"

        text = (
            f"👤 <b>{safe(message.from_user.first_name)}'s Profile</b>\n"
            f"🏎️ <b>{safe(team.name)}</b>\n"
            f"📍 {league_line}\n\n"

            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>Career Stats</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏁 Races:       <b>{total_races}</b>\n"
            f"🏆 Wins:        <b>{total_wins}</b>  ({win_rate:.1f}%)\n"
            f"🥇 Podiums:     <b>{total_podiums}</b>\n"
            f"🔴 Poles:       <b>{total_poles}</b>\n"
            f"⚡ Fastest Laps:<b>{fastest_laps}</b>\n"
            f"💯 Points:      <b>{total_points}</b>\n"
            f"💥 DNFs:        <b>{total_dnf}</b>\n\n"

            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🚗 <b>Car Rating: {car_rating}/100</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚙️ Engine:      {team.engine}/100\n"
            f"🌬️ Aero:        {team.aerodynamics}/100\n"
            f"🏗️ Chassis:     {team.chassis}/100\n"
            f"🔧 Reliability: {team.reliability}/100\n"
            f"🛞 Tyres:       {team.tyres}/100\n"
            f"🔩 Pit Crew:    {team.pit_crew}/100\n\n"

            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💼 <b>Drivers</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{driver_lines}\n"

            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏅 <b>Achievements ({len(achievements)})</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{ach_lines}"
        )

        await message.answer(text)


# ─────────────────────────────────────────────
# /halloffame
# ─────────────────────────────────────────────

@router.message(Command("halloffame"))
async def cmd_halloffame(message: Message):
    async with get_session() as db:
        # All-time top teams by wins
        teams_res = await db.execute(
            select(Team).order_by(Team.wins.desc()).limit(10)
        )
        teams = teams_res.scalars().all()

        if not teams:
            await message.answer("🏛️ Hall of Fame is empty — no races completed yet!")
            return

        # Champion achievements (teams with champion badge)
        champion_res = await db.execute(
            select(TeamAchievement, Team)
            .join(Team, TeamAchievement.team_id == Team.id)
            .where(TeamAchievement.achievement_key == "champion")
            .order_by(TeamAchievement.earned_at.desc())
        )
        champions = champion_res.all()

        text = "🏛️ <b>Hall of Fame</b>\n\n"

        # Season Champions section
        if champions:
            text += "👑 <b>Season Champions</b>\n"
            for ta, t in champions[:8]:
                year = ta.earned_at.strftime("%Y") if ta.earned_at else "—"
                text += f"  🥇 {safe(t.name)}  <i>({year})</i>\n"
            text += "\n"

        # All-time records
        text += "━━━━━━━━━━━━━━━━━━━━\n"
        text += "🏆 <b>All-Time Records</b>\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for i, team in enumerate(teams):
            medal = medals[i] if i < len(medals) else f"{i+1}."
            text += (
                f"{medal} <b>{safe(team.name)}</b>\n"
                f"     🏆 {team.wins}W  🥇 {team.podiums} podiums  💯 {team.total_points or 0} pts\n"
            )

        await message.answer(text)


# ─────────────────────────────────────────────
# /h2h @username  OR  /h2h TeamName
# ─────────────────────────────────────────────

@router.message(Command("h2h"))
async def cmd_h2h(message: Message):
    args = message.text.strip().split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "⚔️ <b>Head to Head</b>\n\n"
            "Usage: <code>/h2h @username</code>\n"
            "or: <code>/h2h TeamName</code>"
        )
        return

    query = args[1].lstrip("@").strip()

    async with get_session() as db:
        # My team
        my_team = await TeamService(db).get_by_owner(message.from_user.id)
        if not my_team:
            await message.answer("❌ You don't have a team. Use /register first.")
            return

        # Find opponent — try username first, then team name
        opp_team = None

        user_res = await db.execute(
            select(User).where(User.username == query)
        )
        opp_user = user_res.scalar_one_or_none()
        if opp_user:
            opp_team = await TeamService(db).get_by_owner(opp_user.id)

        if not opp_team:
            team_res = await db.execute(
                select(Team).where(
                    func.lower(Team.name) == func.lower(query)
                )
            )
            opp_team = team_res.scalar_one_or_none()

        if not opp_team:
            await message.answer(f"❌ Team or user <b>{safe(query)}</b> not found.")
            return

        if opp_team.id == my_team.id:
            await message.answer("❌ You can't compare against yourself!")
            return

        # Races where both teams competed (same race_id)
        my_results_res = await db.execute(
            select(RaceResult).where(RaceResult.team_id == my_team.id)
        )
        my_results = {r.race_id: r for r in my_results_res.scalars().all()}

        opp_results_res = await db.execute(
            select(RaceResult).where(RaceResult.team_id == opp_team.id)
        )
        opp_results = {r.race_id: r for r in opp_results_res.scalars().all()}

        common_races = set(my_results.keys()) & set(opp_results.keys())

        if not common_races:
            await message.answer(
                f"⚔️ <b>{safe(my_team.name)}</b> vs <b>{safe(opp_team.name)}</b>\n\n"
                f"No head-to-head races yet. Join the same league and compete!"
            )
            return

        # Tally
        my_wins = opp_wins = draws = 0
        my_points = opp_points = 0

        for race_id in common_races:
            mr = my_results[race_id]
            or_ = opp_results[race_id]

            my_points += mr.points or 0
            opp_points += or_.points or 0

            # Determine winner by position (DNF = loses)
            my_pos = mr.position if not mr.dnf else 999
            opp_pos = or_.position if not or_.dnf else 999

            if my_pos < opp_pos:
                my_wins += 1
            elif opp_pos < my_pos:
                opp_wins += 1
            else:
                draws += 1

        total = len(common_races)
        my_bar = int((my_wins / total) * 10) if total else 0
        opp_bar = int((opp_wins / total) * 10) if total else 0

        # Determine overall leader
        if my_wins > opp_wins:
            verdict = f"🏆 <b>{safe(my_team.name)}</b> leads the rivalry"
        elif opp_wins > my_wins:
            verdict = f"🏆 <b>{safe(opp_team.name)}</b> leads the rivalry"
        else:
            verdict = "⚖️ Perfectly even rivalry"

        text = (
            f"⚔️ <b>Head to Head</b>\n\n"
            f"<b>{safe(my_team.name)}</b>  vs  <b>{safe(opp_team.name)}</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏁 Races together: <b>{total}</b>\n\n"
            f"🏆 Wins:    <b>{my_wins}</b>  {'🟩' * my_bar}{'⬛' * (10 - my_bar)}  <b>{opp_wins}</b>\n"
            f"💯 Points:  <b>{my_points}</b>  vs  <b>{opp_points}</b>\n"
            f"🤝 Draws:   <b>{draws}</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{verdict}"
        )

        await message.answer(text)
