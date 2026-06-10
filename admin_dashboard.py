"""
F1Game-Bot Admin Dashboard Backend
Run: uvicorn admin_dashboard:app --host 0.0.0.0 --port 8080
"""
import os
import secrets
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt

from sqlalchemy import select, func, update, delete, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# ── Import your bot's models ─────────────────────────────────────────────────
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.models.models import (
    User, League, Team, Driver, TeamDriver, Staff, Race,
    RaceResult, Season, AdminLog, SuspiciousActivity,
    LeagueStatus, RaceStatus
)
from src.core.config import settings

# ── Config ───────────────────────────────────────────────────────────────────
DASHBOARD_SECRET = os.getenv("DASHBOARD_SECRET", secrets.token_hex(32))
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "admin123")  # Change this!
JWT_SECRET = os.getenv("JWT_SECRET", DASHBOARD_SECRET)
JWT_ALGO = "HS256"
JWT_EXPIRE_HOURS = 12

# ── DB setup ─────────────────────────────────────────────────────────────────
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# ── Auth ─────────────────────────────────────────────────────────────────────
security = HTTPBearer(auto_error=False)

def create_token() -> str:
    payload = {"sub": "admin", "exp": datetime.utcnow().timestamp() + JWT_EXPIRE_HOURS * 3600}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
        if payload.get("sub") != "admin":
            raise HTTPException(status_code=401, detail="Invalid token")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="F1Game Admin Dashboard", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Pydantic schemas ──────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    password: str

class BanRequest(BaseModel):
    user_id: int
    reason: Optional[str] = "Admin action"

class MoneyRequest(BaseModel):
    team_id: int
    amount: int  # Can be negative to deduct

class BroadcastRequest(BaseModel):
    message: str
    user_ids: Optional[List[int]] = None  # None = all users

class EditTeamRequest(BaseModel):
    team_id: int
    budget: Optional[int] = None
    reputation: Optional[int] = None
    total_points: Optional[int] = None
    wins: Optional[int] = None
    podiums: Optional[int] = None
    engine: Optional[int] = None
    aerodynamics: Optional[int] = None
    chassis: Optional[int] = None
    reliability: Optional[int] = None

class EditLeagueRequest(BaseModel):
    league_id: int
    status: Optional[str] = None
    max_teams: Optional[int] = None
    description: Optional[str] = None

# ── Auth endpoints ────────────────────────────────────────────────────────────
@app.post("/api/login")
async def login(req: LoginRequest):
    if req.password != DASHBOARD_PASSWORD:
        raise HTTPException(status_code=401, detail="Wrong password")
    token = create_token()
    return {"token": token}

# ── Stats overview ────────────────────────────────────────────────────────────
@app.get("/api/stats")
async def get_stats(db: AsyncSession = Depends(get_db), _=Depends(verify_token)):
    total_users = (await db.execute(select(func.count(User.id)))).scalar()
    total_teams = (await db.execute(select(func.count(Team.id)))).scalar()
    total_leagues = (await db.execute(select(func.count(League.id)))).scalar()
    total_races = (await db.execute(select(func.count(Race.id)))).scalar()
    banned_users = (await db.execute(select(func.count(User.id)).where(User.is_banned == True))).scalar()
    active_leagues = (await db.execute(select(func.count(League.id)).where(League.status == LeagueStatus.ACTIVE))).scalar()
    total_drivers = (await db.execute(select(func.count(Driver.id)))).scalar()

    return {
        "total_users": total_users,
        "total_teams": total_teams,
        "total_leagues": total_leagues,
        "total_races": total_races,
        "banned_users": banned_users,
        "active_leagues": active_leagues,
        "total_drivers": total_drivers,
    }

# ── Users ─────────────────────────────────────────────────────────────────────
@app.get("/api/users")
async def get_users(
    page: int = 1, per_page: int = 20, search: str = "",
    banned_only: bool = False,
    db: AsyncSession = Depends(get_db), _=Depends(verify_token)
):
    q = select(User)
    if search:
        q = q.where(
            (User.username.ilike(f"%{search}%")) |
            (User.first_name.ilike(f"%{search}%"))
        )
    if banned_only:
        q = q.where(User.is_banned == True)
    
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    q = q.order_by(User.created_at.desc()).offset((page-1)*per_page).limit(per_page)
    result = (await db.execute(q)).scalars().all()
    
    users = []
    for u in result:
        team = (await db.execute(select(Team).where(Team.owner_id == u.id))).scalar_one_or_none()
        users.append({
            "id": u.id,
            "username": u.username,
            "first_name": u.first_name,
            "is_banned": u.is_banned,
            "is_admin": u.is_admin,
            "ban_reason": u.ban_reason,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_daily": u.last_daily.isoformat() if u.last_daily else None,
            "command_count": u.command_count,
            "team_name": team.name if team else None,
            "team_id": team.id if team else None,
        })
    
    return {"users": users, "total": total, "pages": (total + per_page - 1) // per_page}

@app.post("/api/users/ban")
async def ban_user(req: BanRequest, db: AsyncSession = Depends(get_db), _=Depends(verify_token)):
    user = (await db.execute(select(User).where(User.id == req.user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_banned = True
    user.ban_reason = req.reason
    await db.commit()
    return {"ok": True, "message": f"User {req.user_id} banned"}

@app.post("/api/users/unban")
async def unban_user(req: BanRequest, db: AsyncSession = Depends(get_db), _=Depends(verify_token)):
    user = (await db.execute(select(User).where(User.id == req.user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_banned = False
    user.ban_reason = None
    await db.commit()
    return {"ok": True, "message": f"User {req.user_id} unbanned"}

@app.delete("/api/users/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db), _=Depends(verify_token)):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()
    return {"ok": True}

# ── Teams ─────────────────────────────────────────────────────────────────────
@app.get("/api/teams")
async def get_teams(
    page: int = 1, per_page: int = 20, search: str = "", league_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db), _=Depends(verify_token)
):
    q = select(Team)
    if search:
        q = q.where(Team.name.ilike(f"%{search}%"))
    if league_id:
        q = q.where(Team.league_id == league_id)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    q = q.order_by(Team.total_points.desc()).offset((page-1)*per_page).limit(per_page)
    result = (await db.execute(q)).scalars().all()

    teams = []
    for t in result:
        owner = (await db.execute(select(User).where(User.id == t.owner_id))).scalar_one_or_none()
        league = (await db.execute(select(League).where(League.id == t.league_id))).scalar_one_or_none() if t.league_id else None
        teams.append({
            "id": t.id,
            "name": t.name,
            "owner_id": t.owner_id,
            "owner_name": owner.first_name if owner else "Unknown",
            "owner_username": owner.username if owner else None,
            "league_id": t.league_id,
            "league_name": league.name if league else None,
            "budget": t.budget,
            "total_points": t.total_points,
            "wins": t.wins,
            "podiums": t.podiums,
            "reputation": t.reputation,
            "engine": t.engine,
            "aerodynamics": t.aerodynamics,
            "chassis": t.chassis,
            "reliability": t.reliability,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        })
    return {"teams": teams, "total": total, "pages": (total + per_page - 1) // per_page}

@app.post("/api/teams/edit")
async def edit_team(req: EditTeamRequest, db: AsyncSession = Depends(get_db), _=Depends(verify_token)):
    team = (await db.execute(select(Team).where(Team.id == req.team_id))).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    fields = ["budget", "reputation", "total_points", "wins", "podiums", "engine", "aerodynamics", "chassis", "reliability"]
    for f in fields:
        val = getattr(req, f)
        if val is not None:
            setattr(team, f, val)
    
    await db.commit()
    return {"ok": True}

@app.post("/api/teams/money")
async def give_money(req: MoneyRequest, db: AsyncSession = Depends(get_db), _=Depends(verify_token)):
    team = (await db.execute(select(Team).where(Team.id == req.team_id))).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    team.budget += req.amount
    if team.budget < 0:
        team.budget = 0
    await db.commit()
    return {"ok": True, "new_budget": team.budget}

@app.delete("/api/teams/{team_id}")
async def delete_team(team_id: int, db: AsyncSession = Depends(get_db), _=Depends(verify_token)):
    team = (await db.execute(select(Team).where(Team.id == team_id))).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    await db.delete(team)
    await db.commit()
    return {"ok": True}

# ── Leagues ───────────────────────────────────────────────────────────────────
@app.get("/api/leagues")
async def get_leagues(
    page: int = 1, per_page: int = 20, search: str = "",
    db: AsyncSession = Depends(get_db), _=Depends(verify_token)
):
    q = select(League)
    if search:
        q = q.where(League.name.ilike(f"%{search}%"))

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    q = q.order_by(League.created_at.desc()).offset((page-1)*per_page).limit(per_page)
    result = (await db.execute(q)).scalars().all()

    leagues = []
    for l in result:
        owner = (await db.execute(select(User).where(User.id == l.owner_id))).scalar_one_or_none()
        team_count = (await db.execute(select(func.count(Team.id)).where(Team.league_id == l.id))).scalar()
        leagues.append({
            "id": l.id,
            "name": l.name,
            "description": l.description,
            "owner_id": l.owner_id,
            "owner_name": owner.first_name if owner else "Unknown",
            "invite_code": l.invite_code,
            "is_public": l.is_public,
            "status": l.status.value if l.status else "unknown",
            "current_season": l.current_season,
            "current_race": l.current_race,
            "max_teams": l.max_teams,
            "team_count": team_count,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        })
    return {"leagues": leagues, "total": total, "pages": (total + per_page - 1) // per_page}

@app.post("/api/leagues/edit")
async def edit_league(req: EditLeagueRequest, db: AsyncSession = Depends(get_db), _=Depends(verify_token)):
    league = (await db.execute(select(League).where(League.id == req.league_id))).scalar_one_or_none()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    
    if req.status:
        league.status = LeagueStatus(req.status)
    if req.max_teams is not None:
        league.max_teams = req.max_teams
    if req.description is not None:
        league.description = req.description
    
    await db.commit()
    return {"ok": True}

@app.delete("/api/leagues/{league_id}")
async def delete_league(league_id: int, db: AsyncSession = Depends(get_db), _=Depends(verify_token)):
    league = (await db.execute(select(League).where(League.id == league_id))).scalar_one_or_none()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    await db.delete(league)
    await db.commit()
    return {"ok": True}

# ── Races ─────────────────────────────────────────────────────────────────────
@app.get("/api/races")
async def get_races(
    league_id: Optional[int] = None, page: int = 1, per_page: int = 20,
    db: AsyncSession = Depends(get_db), _=Depends(verify_token)
):
    q = select(Race)
    if league_id:
        q = q.where(Race.league_id == league_id)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    q = q.order_by(Race.created_at.desc()).offset((page-1)*per_page).limit(per_page)
    result = (await db.execute(q)).scalars().all()

    races = []
    for r in result:
        league = (await db.execute(select(League).where(League.id == r.league_id))).scalar_one_or_none()
        races.append({
            "id": r.id,
            "name": r.name,
            "circuit": r.circuit,
            "league_id": r.league_id,
            "league_name": league.name if league else "Unknown",
            "season": r.season,
            "round_number": r.round_number,
            "status": r.status.value if r.status else "unknown",
            "weather": r.weather.value if r.weather else None,
            "laps": r.laps,
            "scheduled_at": r.scheduled_at.isoformat() if r.scheduled_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {"races": races, "total": total, "pages": (total + per_page - 1) // per_page}

# ── Admin logs ────────────────────────────────────────────────────────────────
@app.get("/api/logs")
async def get_logs(
    page: int = 1, per_page: int = 30,
    db: AsyncSession = Depends(get_db), _=Depends(verify_token)
):
    q = select(AdminLog).order_by(AdminLog.created_at.desc())
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    q = q.offset((page-1)*per_page).limit(per_page)
    result = (await db.execute(q)).scalars().all()

    logs = []
    for log in result:
        admin = (await db.execute(select(User).where(User.id == log.admin_id))).scalar_one_or_none()
        logs.append({
            "id": log.id,
            "admin_id": log.admin_id,
            "admin_name": admin.first_name if admin else "Unknown",
            "action": log.action,
            "target_id": log.target_id if hasattr(log, 'target_id') else None,
            "details": log.details if hasattr(log, 'details') else None,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })
    return {"logs": logs, "total": total}

@app.get("/api/suspicious")
async def get_suspicious(
    page: int = 1, per_page: int = 30,
    db: AsyncSession = Depends(get_db), _=Depends(verify_token)
):
    q = select(SuspiciousActivity).order_by(SuspiciousActivity.created_at.desc())
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    q = q.offset((page-1)*per_page).limit(per_page)
    result = (await db.execute(q)).scalars().all()

    items = []
    for s in result:
        user = (await db.execute(select(User).where(User.id == s.user_id))).scalar_one_or_none()
        items.append({
            "id": s.id,
            "user_id": s.user_id,
            "user_name": user.first_name if user else "Unknown",
            "activity_type": s.activity_type,
            "details": s.details if hasattr(s, 'details') else None,
            "severity": s.severity if hasattr(s, 'severity') else "low",
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    return {"items": items, "total": total}

# ── Drivers ───────────────────────────────────────────────────────────────────
@app.get("/api/drivers")
async def get_drivers(
    page: int = 1, per_page: int = 20, search: str = "", free_agents: bool = False,
    db: AsyncSession = Depends(get_db), _=Depends(verify_token)
):
    q = select(Driver)
    if search:
        q = q.where(Driver.name.ilike(f"%{search}%"))
    if free_agents:
        # Drivers not in any TeamDriver
        assigned_ids = select(TeamDriver.driver_id)
        q = q.where(~Driver.id.in_(assigned_ids))

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    q = q.order_by(Driver.overall_rating.desc()).offset((page-1)*per_page).limit(per_page)
    result = (await db.execute(q)).scalars().all()

    drivers = []
    for d in result:
        team_driver = (await db.execute(select(TeamDriver).where(TeamDriver.driver_id == d.id))).scalar_one_or_none()
        team = None
        if team_driver:
            team = (await db.execute(select(Team).where(Team.id == team_driver.team_id))).scalar_one_or_none()
        drivers.append({
            "id": d.id,
            "name": d.name,
            "nationality": d.nationality if hasattr(d, 'nationality') else None,
            "overall_rating": d.overall_rating,
            "pace": d.pace if hasattr(d, 'pace') else None,
            "racecraft": d.racecraft if hasattr(d, 'racecraft') else None,
            "consistency": d.consistency if hasattr(d, 'consistency') else None,
            "salary": d.salary if hasattr(d, 'salary') else None,
            "team_name": team.name if team else None,
            "is_free_agent": team is None,
        })
    return {"drivers": drivers, "total": total, "pages": (total + per_page - 1) // per_page}

# ── Broadcast via bot ─────────────────────────────────────────────────────────
@app.post("/api/broadcast")
async def broadcast_message(req: BroadcastRequest, db: AsyncSession = Depends(get_db), _=Depends(verify_token)):
    """
    Returns user IDs to broadcast to. 
    The actual Telegram sending is done by a separate bot script.
    This endpoint stores a pending broadcast that the bot processes.
    """
    if req.user_ids:
        target_ids = req.user_ids
    else:
        result = await db.execute(select(User.id).where(User.is_banned == False))
        target_ids = [row[0] for row in result.fetchall()]
    
    # Store broadcast in DB or write to file for bot to pick up
    broadcast_file = "/tmp/pending_broadcast.json"
    import json
    with open(broadcast_file, "w") as f:
        json.dump({"message": req.message, "user_ids": target_ids, "timestamp": datetime.utcnow().isoformat()}, f)
    
    return {"ok": True, "target_count": len(target_ids), "note": "Broadcast queued. Bot will process it."}

# ── Raw SQL query (for power users) ──────────────────────────────────────────
@app.post("/api/query")
async def raw_query(request: Request, db: AsyncSession = Depends(get_db), _=Depends(verify_token)):
    body = await request.json()
    sql = body.get("sql", "").strip()
    
    # Safety: only SELECT allowed
    if not sql.upper().startswith("SELECT"):
        raise HTTPException(status_code=400, detail="Only SELECT queries allowed")
    
    try:
        result = await db.execute(text(sql))
        rows = result.fetchall()
        columns = list(result.keys())
        return {"columns": columns, "rows": [list(r) for r in rows[:500]]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ── Serve dashboard HTML ──────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    with open(os.path.join(os.path.dirname(__file__), "admin_dashboard.html")) as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("DASHBOARD_PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
