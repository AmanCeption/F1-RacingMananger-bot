"""
F1 Bot Admin Dashboard — FastAPI
Runs alongside the bot on a separate port (10001)
Protected by DASHBOARD_SECRET env var
"""
import os
from datetime import datetime, timedelta
from typing import Optional

from aiohttp import web
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.session import async_session_maker
from src.models.models import (
    User, Team, League, Race, RaceResult,
    AdminLog, SuspiciousActivity,
    LeagueStatus, RaceStatus
)
from src.core.config import settings

DASHBOARD_SECRET = os.getenv("DASHBOARD_SECRET", "admin123")


async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        return session


# ── Auth middleware ──────────────────────────────────────

async def check_auth(request: web.Request) -> bool:
    token = request.cookies.get("dash_token") or request.headers.get("X-Dashboard-Token")
    return token == DASHBOARD_SECRET


# ── API Handlers ─────────────────────────────────────────

async def handle_login(request: web.Request) -> web.Response:
    data = await request.post()
    password = data.get("password", "")
    if password == DASHBOARD_SECRET:
        response = web.HTTPFound("/dashboard/")
        response.set_cookie("dash_token", DASHBOARD_SECRET, max_age=86400 * 7, httponly=True)
        return response
    return web.Response(
        content_type="text/html",
        text=LOGIN_HTML.replace("{{ERROR}}", '<p class="error">Wrong password!</p>')
    )


async def handle_stats_api(request: web.Request) -> web.Response:
    if not await check_auth(request):
        return web.json_response({"error": "unauthorized"}, status=401)

    async with async_session_maker() as db:
        # Total users
        total_users = (await db.execute(select(func.count(User.id)))).scalar()
        banned_users = (await db.execute(select(func.count(User.id)).where(User.is_banned == True))).scalar()

        # New users (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        new_users = (await db.execute(
            select(func.count(User.id)).where(User.created_at >= week_ago)
        )).scalar()

        # Teams
        total_teams = (await db.execute(select(func.count(Team.id)))).scalar()

        # Leagues
        total_leagues = (await db.execute(select(func.count(League.id)))).scalar()
        active_leagues = (await db.execute(
            select(func.count(League.id)).where(League.status == LeagueStatus.ACTIVE)
        )).scalar()

        # Races
        total_races = (await db.execute(select(func.count(Race.id)))).scalar()
        finished_races = (await db.execute(
            select(func.count(Race.id)).where(Race.status == RaceStatus.FINISHED)
        )).scalar()

        # Total budget in game (sum of all teams)
        total_budget = (await db.execute(select(func.sum(Team.budget)))).scalar() or 0

        # Suspicious activity (last 24h)
        day_ago = datetime.utcnow() - timedelta(days=1)
        sus_count = (await db.execute(
            select(func.count(SuspiciousActivity.id)).where(SuspiciousActivity.created_at >= day_ago)
        )).scalar()

    return web.json_response({
        "users": {"total": total_users, "banned": banned_users, "new_7d": new_users},
        "teams": {"total": total_teams},
        "leagues": {"total": total_leagues, "active": active_leagues},
        "races": {"total": total_races, "finished": finished_races},
        "economy": {"total_budget": total_budget},
        "security": {"sus_24h": sus_count},
    })


async def handle_users_api(request: web.Request) -> web.Response:
    if not await check_auth(request):
        return web.json_response({"error": "unauthorized"}, status=401)

    page = int(request.query.get("page", 1))
    search = request.query.get("search", "").strip()
    per_page = 20

    async with async_session_maker() as db:
        q = select(User).order_by(User.created_at.desc())
        if search:
            q = q.where(
                (User.username.ilike(f"%{search}%")) |
                (User.first_name.ilike(f"%{search}%"))
            )
        q = q.offset((page - 1) * per_page).limit(per_page)
        result = await db.execute(q)
        users = result.scalars().all()

        # Get team info for each user
        user_list = []
        for u in users:
            team_res = await db.execute(select(Team).where(Team.owner_id == u.id))
            team = team_res.scalar_one_or_none()
            user_list.append({
                "id": u.id,
                "username": u.username or "—",
                "first_name": u.first_name,
                "is_banned": u.is_banned,
                "ban_reason": u.ban_reason or "",
                "team": team.name if team else None,
                "created_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "—",
            })

    return web.json_response({"users": user_list, "page": page})


async def handle_leagues_api(request: web.Request) -> web.Response:
    if not await check_auth(request):
        return web.json_response({"error": "unauthorized"}, status=401)

    async with async_session_maker() as db:
        result = await db.execute(select(League).order_by(League.created_at.desc()))
        leagues = result.scalars().all()

        league_list = []
        for lg in leagues:
            team_count = (await db.execute(
                select(func.count(Team.id)).where(Team.league_id == lg.id)
            )).scalar()
            league_list.append({
                "id": lg.id,
                "name": lg.name,
                "status": lg.status.value,
                "teams": team_count,
                "season": lg.current_season,
                "race": lg.current_race,
                "invite_code": lg.invite_code,
                "created_at": lg.created_at.strftime("%Y-%m-%d") if lg.created_at else "—",
            })

    return web.json_response({"leagues": league_list})


async def handle_logs_api(request: web.Request) -> web.Response:
    if not await check_auth(request):
        return web.json_response({"error": "unauthorized"}, status=401)

    async with async_session_maker() as db:
        result = await db.execute(
            select(AdminLog).order_by(AdminLog.created_at.desc()).limit(50)
        )
        logs = result.scalars().all()

        log_list = []
        for log in logs:
            admin_res = await db.execute(select(User).where(User.id == log.admin_id))
            admin = admin_res.scalar_one_or_none()
            log_list.append({
                "id": log.id,
                "admin": admin.first_name if admin else str(log.admin_id),
                "action": log.action,
                "target_id": log.target_id,
                "details": log.details or "",
                "created_at": log.created_at.strftime("%Y-%m-%d %H:%M") if log.created_at else "—",
            })

    return web.json_response({"logs": log_list})


async def handle_sus_api(request: web.Request) -> web.Response:
    if not await check_auth(request):
        return web.json_response({"error": "unauthorized"}, status=401)

    async with async_session_maker() as db:
        result = await db.execute(
            select(SuspiciousActivity).order_by(SuspiciousActivity.created_at.desc()).limit(50)
        )
        activities = result.scalars().all()

        sus_list = []
        for a in activities:
            user_res = await db.execute(select(User).where(User.id == a.user_id))
            user = user_res.scalar_one_or_none()
            sus_list.append({
                "id": a.id,
                "user": user.first_name if user else str(a.user_id),
                "user_id": a.user_id,
                "type": a.activity_type,
                "severity": a.severity,
                "details": a.details or "",
                "created_at": a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else "—",
            })

    return web.json_response({"activities": sus_list})


async def handle_ban_api(request: web.Request) -> web.Response:
    """Ban/unban a user"""
    if not await check_auth(request):
        return web.json_response({"error": "unauthorized"}, status=401)

    data = await request.json()
    user_id = data.get("user_id")
    action = data.get("action")  # "ban" or "unban"
    reason = data.get("reason", "Admin action via dashboard")

    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return web.json_response({"error": "User not found"}, status=404)

        if action == "ban":
            user.is_banned = True
            user.ban_reason = reason
        else:
            user.is_banned = False
            user.ban_reason = None

        await db.commit()

    return web.json_response({"success": True, "action": action, "user_id": user_id})


async def handle_broadcast_api(request: web.Request) -> web.Response:
    """Send broadcast via dashboard — queues to Redis or stores for bot to pick up"""
    if not await check_auth(request):
        return web.json_response({"error": "unauthorized"}, status=401)

    data = await request.json()
    message = data.get("message", "").strip()
    if not message:
        return web.json_response({"error": "Empty message"}, status=400)

    # Store broadcast in DB as a pending admin action
    # Bot's scheduler will pick it up, or owner can /broadcast from Telegram
    return web.json_response({
        "success": True,
        "note": "Use /broadcast command in Telegram bot to send to all users",
        "message": message
    })


# ── Main Dashboard Page ──────────────────────────────────

async def handle_dashboard(request: web.Request) -> web.Response:
    if not await check_auth(request):
        return web.Response(content_type="text/html", text=LOGIN_HTML.replace("{{ERROR}}", ""))
    return web.Response(content_type="text/html", text=DASHBOARD_HTML)


async def handle_logout(request: web.Request) -> web.Response:
    response = web.HTTPFound("/dashboard/")
    response.del_cookie("dash_token")
    return response


# ── HTML Templates ────────────────────────────────────────

LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>F1 Bot — Admin Login</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Titillium+Web:wght@300;400;600;700;900&display=swap');
  *{margin:0;padding:0;box-sizing:border-box}
  body{background:#0a0a0f;font-family:'Titillium Web',sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}
  .login-wrap{width:380px}
  .logo{text-align:center;margin-bottom:40px}
  .logo span{font-size:13px;letter-spacing:6px;color:#e10600;text-transform:uppercase;font-weight:700}
  .logo h1{font-size:36px;font-weight:900;color:#fff;letter-spacing:2px;margin-top:4px}
  .card{background:#13131a;border:1px solid #1e1e2e;border-radius:4px;padding:36px}
  .card h2{color:#fff;font-size:16px;font-weight:600;letter-spacing:3px;text-transform:uppercase;margin-bottom:28px;text-align:center}
  input[type=password]{width:100%;background:#0a0a0f;border:1px solid #2a2a3e;color:#fff;font-family:inherit;font-size:15px;padding:14px 16px;border-radius:3px;outline:none;transition:border .2s}
  input:focus{border-color:#e10600}
  button{width:100%;margin-top:16px;background:#e10600;color:#fff;font-family:inherit;font-size:14px;font-weight:700;letter-spacing:3px;text-transform:uppercase;padding:14px;border:none;border-radius:3px;cursor:pointer;transition:background .2s}
  button:hover{background:#ff1a0e}
  .error{color:#e10600;font-size:13px;margin-top:12px;text-align:center}
</style>
</head>
<body>
<div class="login-wrap">
  <div class="logo">
    <span>AmanCeption</span>
    <h1>F1 ADMIN</h1>
  </div>
  <div class="card">
    <h2>Access Dashboard</h2>
    <form method="POST" action="/dashboard/login">
      <input type="password" name="password" placeholder="Dashboard Password" autofocus>
      <button type="submit">Enter →</button>
      {{ERROR}}
    </form>
  </div>
</div>
</body>
</html>"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>F1 Bot Admin</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Titillium+Web:wght@300;400;600;700;900&display=swap');
  *{margin:0;padding:0;box-sizing:border-box}
  :root{
    --red:#e10600;--dark:#0a0a0f;--card:#13131a;--border:#1e1e2e;
    --text:#e8e8f0;--muted:#6b6b8a;--green:#00d46a;--yellow:#ffd700;--blue:#0090d8
  }
  body{background:var(--dark);color:var(--text);font-family:'Titillium Web',sans-serif;min-height:100vh}

  /* Layout */
  .sidebar{position:fixed;left:0;top:0;bottom:0;width:220px;background:var(--card);border-right:1px solid var(--border);display:flex;flex-direction:column;z-index:100}
  .sidebar-logo{padding:24px 20px;border-bottom:1px solid var(--border)}
  .sidebar-logo span{font-size:10px;letter-spacing:5px;color:var(--red);text-transform:uppercase;font-weight:700}
  .sidebar-logo h1{font-size:22px;font-weight:900;color:#fff;letter-spacing:1px}
  nav{flex:1;padding:16px 0}
  nav a{display:flex;align-items:center;gap:12px;padding:12px 20px;color:var(--muted);text-decoration:none;font-size:14px;font-weight:600;letter-spacing:1px;text-transform:uppercase;transition:all .2s;border-left:3px solid transparent}
  nav a:hover{color:var(--text);background:rgba(255,255,255,.03)}
  nav a.active{color:#fff;border-left-color:var(--red);background:rgba(225,6,0,.06)}
  nav a .icon{font-size:16px;width:20px;text-align:center}
  .sidebar-footer{padding:16px 20px;border-top:1px solid var(--border)}
  .sidebar-footer a{color:var(--muted);font-size:12px;text-decoration:none;letter-spacing:1px}
  .sidebar-footer a:hover{color:var(--red)}

  .main{margin-left:220px;padding:32px;min-height:100vh}
  .page-header{margin-bottom:32px}
  .page-header h2{font-size:24px;font-weight:900;letter-spacing:2px;text-transform:uppercase;color:#fff}
  .page-header p{color:var(--muted);font-size:13px;margin-top:4px}

  /* Stat Cards */
  .stats-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:16px;margin-bottom:32px}
  .stat-card{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:20px;position:relative;overflow:hidden}
  .stat-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--red)}
  .stat-card.green::before{background:var(--green)}
  .stat-card.blue::before{background:var(--blue)}
  .stat-card.yellow::before{background:var(--yellow)}
  .stat-label{font-size:10px;letter-spacing:3px;text-transform:uppercase;color:var(--muted);font-weight:700}
  .stat-value{font-size:32px;font-weight:900;color:#fff;margin-top:8px;line-height:1}
  .stat-sub{font-size:12px;color:var(--muted);margin-top:6px}

  /* Table */
  .table-wrap{background:var(--card);border:1px solid var(--border);border-radius:4px;overflow:hidden;margin-bottom:24px}
  .table-header{display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid var(--border)}
  .table-title{font-size:13px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#fff}
  .search-box{background:var(--dark);border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:13px;padding:8px 14px;border-radius:3px;outline:none;width:220px}
  .search-box:focus{border-color:var(--red)}
  table{width:100%;border-collapse:collapse}
  th{font-size:10px;letter-spacing:2px;text-transform:uppercase;color:var(--muted);font-weight:700;padding:12px 20px;text-align:left;border-bottom:1px solid var(--border)}
  td{padding:12px 20px;font-size:14px;border-bottom:1px solid rgba(255,255,255,.04)}
  tr:last-child td{border:none}
  tr:hover td{background:rgba(255,255,255,.02)}

  /* Badges */
  .badge{display:inline-block;padding:2px 10px;border-radius:2px;font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase}
  .badge-red{background:rgba(225,6,0,.15);color:#ff4040}
  .badge-green{background:rgba(0,212,106,.15);color:#00d46a}
  .badge-yellow{background:rgba(255,215,0,.15);color:#ffd700}
  .badge-blue{background:rgba(0,144,216,.15);color:#0090d8}
  .badge-grey{background:rgba(107,107,138,.15);color:#9090b0}

  /* Buttons */
  .btn{display:inline-flex;align-items:center;gap:6px;padding:7px 16px;border-radius:3px;font-family:inherit;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;cursor:pointer;border:none;transition:all .15s}
  .btn-red{background:var(--red);color:#fff}
  .btn-red:hover{background:#ff1a0e}
  .btn-outline{background:transparent;color:var(--muted);border:1px solid var(--border)}
  .btn-outline:hover{color:#fff;border-color:#fff}
  .btn-green{background:rgba(0,212,106,.15);color:var(--green);border:1px solid rgba(0,212,106,.3)}
  .btn-green:hover{background:rgba(0,212,106,.25)}

  /* Pages */
  .page{display:none}
  .page.active{display:block}

  /* Modal */
  .modal-bg{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:999;align-items:center;justify-content:center}
  .modal-bg.open{display:flex}
  .modal{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:28px;width:420px;max-width:90vw}
  .modal h3{font-size:16px;font-weight:700;letter-spacing:2px;text-transform:uppercase;margin-bottom:20px}
  .modal input,.modal textarea{width:100%;background:var(--dark);border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:14px;padding:12px 14px;border-radius:3px;outline:none;margin-bottom:12px}
  .modal input:focus,.modal textarea:focus{border-color:var(--red)}
  .modal textarea{height:100px;resize:vertical}
  .modal-actions{display:flex;gap:10px;justify-content:flex-end;margin-top:8px}

  /* Broadcast */
  .broadcast-box{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:24px;margin-bottom:24px}
  .broadcast-box h3{font-size:13px;font-weight:700;letter-spacing:2px;text-transform:uppercase;margin-bottom:16px;color:#fff}
  .broadcast-box textarea{width:100%;background:var(--dark);border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:14px;padding:14px;border-radius:3px;outline:none;height:120px;resize:vertical}
  .broadcast-box textarea:focus{border-color:var(--red)}
  .broadcast-note{font-size:12px;color:var(--muted);margin-top:10px}

  /* Toast */
  .toast{position:fixed;bottom:24px;right:24px;background:#13131a;border:1px solid var(--border);border-radius:4px;padding:14px 20px;font-size:14px;transform:translateY(80px);opacity:0;transition:all .3s;z-index:9999}
  .toast.show{transform:translateY(0);opacity:1}

  /* Loading */
  .loading{color:var(--muted);font-size:14px;padding:24px 20px}
  .dot-pulse::after{content:'...';animation:dots 1.2s infinite}
  @keyframes dots{0%{content:'.'}40%{content:'..'}80%{content:'...'}}

  /* Responsive */
  @media(max-width:768px){
    .sidebar{width:100%;height:auto;position:relative;flex-direction:row;flex-wrap:wrap}
    .main{margin-left:0}
    .stats-grid{grid-template-columns:1fr 1fr}
  }
</style>
</head>
<body>

<aside class="sidebar">
  <div class="sidebar-logo">
    <span>AmanCeption</span>
    <h1>F1 ADMIN</h1>
  </div>
  <nav>
    <a href="#" class="active" onclick="showPage('overview',this)">
      <span class="icon">🏎</span> Overview
    </a>
    <a href="#" onclick="showPage('users',this)">
      <span class="icon">👥</span> Users
    </a>
    <a href="#" onclick="showPage('leagues',this)">
      <span class="icon">🏆</span> Leagues
    </a>
    <a href="#" onclick="showPage('logs',this)">
      <span class="icon">📋</span> Admin Logs
    </a>
    <a href="#" onclick="showPage('security',this)">
      <span class="icon">🛡</span> Anti-Cheat
    </a>
    <a href="#" onclick="showPage('broadcast',this)">
      <span class="icon">📡</span> Broadcast
    </a>
  </nav>
  <div class="sidebar-footer">
    <a href="/dashboard/logout">⎋ Logout</a>
  </div>
</aside>

<main class="main">

  <!-- OVERVIEW -->
  <div id="page-overview" class="page active">
    <div class="page-header">
      <h2>Overview</h2>
      <p>F1 Bot live stats</p>
    </div>
    <div class="stats-grid" id="stats-grid">
      <div class="loading dot-pulse">Loading stats</div>
    </div>
  </div>

  <!-- USERS -->
  <div id="page-users" class="page">
    <div class="page-header">
      <h2>Users</h2>
      <p>All registered users</p>
    </div>
    <div class="table-wrap">
      <div class="table-header">
        <span class="table-title">User List</span>
        <input class="search-box" id="user-search" placeholder="Search name / username…" oninput="searchUsers(this.value)">
      </div>
      <div id="users-table-body">
        <div class="loading dot-pulse">Loading users</div>
      </div>
    </div>
    <div id="users-pagination" style="display:flex;gap:8px;align-items:center"></div>
  </div>

  <!-- LEAGUES -->
  <div id="page-leagues" class="page">
    <div class="page-header">
      <h2>Leagues</h2>
      <p>All active and past leagues</p>
    </div>
    <div class="table-wrap">
      <div class="table-header">
        <span class="table-title">League List</span>
      </div>
      <div id="leagues-table-body">
        <div class="loading dot-pulse">Loading leagues</div>
      </div>
    </div>
  </div>

  <!-- LOGS -->
  <div id="page-logs" class="page">
    <div class="page-header">
      <h2>Admin Logs</h2>
      <p>Recent admin actions (last 50)</p>
    </div>
    <div class="table-wrap">
      <div class="table-header">
        <span class="table-title">Action Log</span>
      </div>
      <div id="logs-table-body">
        <div class="loading dot-pulse">Loading logs</div>
      </div>
    </div>
  </div>

  <!-- SECURITY -->
  <div id="page-security" class="page">
    <div class="page-header">
      <h2>Anti-Cheat</h2>
      <p>Suspicious activity (last 50)</p>
    </div>
    <div class="table-wrap">
      <div class="table-header">
        <span class="table-title">Flagged Activity</span>
      </div>
      <div id="sus-table-body">
        <div class="loading dot-pulse">Loading activity</div>
      </div>
    </div>
  </div>

  <!-- BROADCAST -->
  <div id="page-broadcast" class="page">
    <div class="page-header">
      <h2>Broadcast</h2>
      <p>Send message to all users</p>
    </div>
    <div class="broadcast-box">
      <h3>📡 Message All Users</h3>
      <textarea id="broadcast-text" placeholder="Type your announcement here…&#10;&#10;Example: New season starting tomorrow! Prepare your teams 🏎️"></textarea>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-top:12px">
        <button class="btn btn-red" onclick="sendBroadcast()">Copy for /broadcast →</button>
        <span id="broadcast-chars" style="font-size:12px;color:var(--muted)">0 chars</span>
      </div>
      <p class="broadcast-note">⚡ This copies the command to clipboard. Paste it in your Telegram bot chat to send to all users.</p>
    </div>
  </div>

</main>

<!-- Ban Modal -->
<div class="modal-bg" id="ban-modal">
  <div class="modal">
    <h3 id="ban-modal-title">Ban User</h3>
    <input type="hidden" id="ban-user-id">
    <input type="hidden" id="ban-action">
    <input id="ban-reason" placeholder="Ban reason (optional)">
    <div class="modal-actions">
      <button class="btn btn-outline" onclick="closeModal()">Cancel</button>
      <button class="btn btn-red" onclick="confirmBan()">Confirm</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
let currentUsersPage = 1;
let currentSearch = '';

// ── Navigation ─────────────────────────────────
function showPage(name, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('nav a').forEach(a => a.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  el.classList.add('active');

  if (name === 'overview') loadStats();
  if (name === 'users') loadUsers(1);
  if (name === 'leagues') loadLeagues();
  if (name === 'logs') loadLogs();
  if (name === 'security') loadSus();
}

// ── Toast ───────────────────────────────────────
function showToast(msg, isError) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.borderColor = isError ? 'var(--red)' : 'var(--green)';
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3000);
}

// ── Stats ───────────────────────────────────────
async function loadStats() {
  const res = await fetch('/dashboard/api/stats');
  const d = await res.json();
  document.getElementById('stats-grid').innerHTML = `
    <div class="stat-card">
      <div class="stat-label">Total Users</div>
      <div class="stat-value">${d.users.total}</div>
      <div class="stat-sub">+${d.users.new_7d} this week</div>
    </div>
    <div class="stat-card red">
      <div class="stat-label">Banned</div>
      <div class="stat-value">${d.users.banned}</div>
      <div class="stat-sub">Users blocked</div>
    </div>
    <div class="stat-card green">
      <div class="stat-label">Active Leagues</div>
      <div class="stat-value">${d.leagues.active}</div>
      <div class="stat-sub">${d.leagues.total} total</div>
    </div>
    <div class="stat-card blue">
      <div class="stat-label">Teams</div>
      <div class="stat-value">${d.teams.total}</div>
      <div class="stat-sub">Across all leagues</div>
    </div>
    <div class="stat-card yellow">
      <div class="stat-label">Races Run</div>
      <div class="stat-value">${d.races.finished}</div>
      <div class="stat-sub">${d.races.total} scheduled</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Total In-Game $</div>
      <div class="stat-value">$${(d.economy.total_budget/1e9).toFixed(1)}B</div>
      <div class="stat-sub">Combined budgets</div>
    </div>
    <div class="stat-card ${d.security.sus_24h > 0 ? 'red' : 'green'}">
      <div class="stat-label">Sus Activity</div>
      <div class="stat-value">${d.security.sus_24h}</div>
      <div class="stat-sub">Last 24 hours</div>
    </div>
  `;
}

// ── Users ───────────────────────────────────────
async function loadUsers(page, search) {
  if(search !== undefined) currentSearch = search;
  if(page) currentUsersPage = page;
  const res = await fetch(`/dashboard/api/users?page=${currentUsersPage}&search=${encodeURIComponent(currentSearch)}`);
  const d = await res.json();

  if (!d.users.length) {
    document.getElementById('users-table-body').innerHTML = '<div class="loading">No users found</div>';
    return;
  }

  document.getElementById('users-table-body').innerHTML = `
    <table>
      <thead><tr>
        <th>Telegram ID</th><th>Name</th><th>Username</th><th>Team</th><th>Status</th><th>Joined</th><th>Actions</th>
      </tr></thead>
      <tbody>${d.users.map(u => `
        <tr>
          <td><code style="color:var(--muted);font-size:12px">${u.id}</code></td>
          <td><strong>${u.first_name}</strong></td>
          <td>${u.username}</td>
          <td>${u.team ? `<span class="badge badge-blue">${u.team}</span>` : '<span style="color:var(--muted)">—</span>'}</td>
          <td>${u.is_banned
            ? `<span class="badge badge-red">BANNED</span>`
            : `<span class="badge badge-green">Active</span>`}</td>
          <td style="color:var(--muted);font-size:12px">${u.created_at}</td>
          <td>
            ${u.is_banned
              ? `<button class="btn btn-green" onclick="openUnban(${u.id},'${u.first_name}')">Unban</button>`
              : `<button class="btn btn-red" onclick="openBan(${u.id},'${u.first_name}')">Ban</button>`}
          </td>
        </tr>`).join('')}
      </tbody>
    </table>`;

  document.getElementById('users-pagination').innerHTML = `
    <button class="btn btn-outline" onclick="loadUsers(${currentUsersPage-1})" ${currentUsersPage<=1?'disabled':''}>← Prev</button>
    <span style="color:var(--muted);font-size:13px">Page ${currentUsersPage}</span>
    <button class="btn btn-outline" onclick="loadUsers(${currentUsersPage+1})" ${d.users.length<20?'disabled':''}>Next →</button>`;
}

let searchTimeout;
function searchUsers(val) {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => loadUsers(1, val), 400);
}

// ── Leagues ─────────────────────────────────────
async function loadLeagues() {
  const res = await fetch('/dashboard/api/leagues');
  const d = await res.json();

  const statusBadge = s => {
    const map = {active:'green',waiting:'yellow',paused:'grey',finished:'grey'};
    return `<span class="badge badge-${map[s]||'grey'}">${s.toUpperCase()}</span>`;
  };

  document.getElementById('leagues-table-body').innerHTML = `
    <table>
      <thead><tr><th>ID</th><th>Name</th><th>Status</th><th>Teams</th><th>Season</th><th>Race</th><th>Invite</th><th>Created</th></tr></thead>
      <tbody>${d.leagues.map(lg => `
        <tr>
          <td style="color:var(--muted)">${lg.id}</td>
          <td><strong>${lg.name}</strong></td>
          <td>${statusBadge(lg.status)}</td>
          <td>${lg.teams}</td>
          <td>${lg.season}</td>
          <td>${lg.race}</td>
          <td><code style="font-size:12px;color:var(--blue)">${lg.invite_code}</code></td>
          <td style="color:var(--muted);font-size:12px">${lg.created_at}</td>
        </tr>`).join('')}
      </tbody>
    </table>`;
}

// ── Admin Logs ───────────────────────────────────
async function loadLogs() {
  const res = await fetch('/dashboard/api/logs');
  const d = await res.json();
  document.getElementById('logs-table-body').innerHTML = `
    <table>
      <thead><tr><th>Time</th><th>Admin</th><th>Action</th><th>Target</th><th>Details</th></tr></thead>
      <tbody>${d.logs.map(l => `
        <tr>
          <td style="color:var(--muted);font-size:12px">${l.created_at}</td>
          <td><strong>${l.admin}</strong></td>
          <td><span class="badge badge-blue">${l.action}</span></td>
          <td style="color:var(--muted)">${l.target_id || '—'}</td>
          <td style="font-size:13px">${l.details}</td>
        </tr>`).join('')}
      </tbody>
    </table>`;
}

// ── Anti-Cheat ───────────────────────────────────
async function loadSus() {
  const res = await fetch('/dashboard/api/suspicious');
  const d = await res.json();
  const sevBadge = s => {
    const map = {high:'red',medium:'yellow',low:'grey'};
    return `<span class="badge badge-${map[s]||'grey'}">${s.toUpperCase()}</span>`;
  };
  document.getElementById('sus-table-body').innerHTML = `
    <table>
      <thead><tr><th>Time</th><th>User</th><th>Type</th><th>Severity</th><th>Details</th><th>Action</th></tr></thead>
      <tbody>${d.activities.map(a => `
        <tr>
          <td style="color:var(--muted);font-size:12px">${a.created_at}</td>
          <td><strong>${a.user}</strong> <span style="color:var(--muted);font-size:11px">${a.user_id}</span></td>
          <td style="font-size:13px">${a.type}</td>
          <td>${sevBadge(a.severity)}</td>
          <td style="font-size:12px;color:var(--muted)">${a.details}</td>
          <td><button class="btn btn-red" onclick="openBan(${a.user_id},'User ${a.user_id}')">Ban</button></td>
        </tr>`).join('')}
      </tbody>
    </table>`;
}

// ── Ban / Unban ───────────────────────────────────
function openBan(userId, name) {
  document.getElementById('ban-user-id').value = userId;
  document.getElementById('ban-action').value = 'ban';
  document.getElementById('ban-modal-title').textContent = 'Ban ' + name;
  document.getElementById('ban-reason').value = '';
  document.getElementById('ban-reason').style.display = 'block';
  document.getElementById('ban-modal').classList.add('open');
}
function openUnban(userId, name) {
  document.getElementById('ban-user-id').value = userId;
  document.getElementById('ban-action').value = 'unban';
  document.getElementById('ban-modal-title').textContent = 'Unban ' + name + '?';
  document.getElementById('ban-reason').style.display = 'none';
  document.getElementById('ban-modal').classList.add('open');
}
function closeModal() {
  document.getElementById('ban-modal').classList.remove('open');
}
async function confirmBan() {
  const userId = document.getElementById('ban-user-id').value;
  const action = document.getElementById('ban-action').value;
  const reason = document.getElementById('ban-reason').value;
  const res = await fetch('/dashboard/api/ban', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({user_id: parseInt(userId), action, reason})
  });
  const d = await res.json();
  closeModal();
  if (d.success) {
    showToast(action === 'ban' ? '🚫 User banned' : '✅ User unbanned');
    loadUsers(currentUsersPage);
  } else {
    showToast('Error: ' + (d.error||'Unknown'), true);
  }
}

// ── Broadcast ─────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const ta = document.getElementById('broadcast-text');
  if(ta) ta.addEventListener('input', () => {
    document.getElementById('broadcast-chars').textContent = ta.value.length + ' chars';
  });
});

function sendBroadcast() {
  const msg = document.getElementById('broadcast-text').value.trim();
  if (!msg) { showToast('Write a message first!', true); return; }
  const cmd = '/broadcast ' + msg;
  navigator.clipboard.writeText(cmd).then(() => {
    showToast('✅ Copied! Paste in Telegram bot chat');
  });
}

// ── Init ──────────────────────────────────────────
loadStats();
</script>
</body>
</html>"""


# ── App Factory ───────────────────────────────────────────

def create_dashboard_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/dashboard/", handle_dashboard)
    app.router.add_get("/dashboard", handle_dashboard)
    app.router.add_post("/dashboard/login", handle_login)
    app.router.add_get("/dashboard/logout", handle_logout)
    app.router.add_get("/dashboard/api/stats", handle_stats_api)
    app.router.add_get("/dashboard/api/users", handle_users_api)
    app.router.add_get("/dashboard/api/leagues", handle_leagues_api)
    app.router.add_get("/dashboard/api/logs", handle_logs_api)
    app.router.add_get("/dashboard/api/suspicious", handle_sus_api)
    app.router.add_post("/dashboard/api/ban", handle_ban_api)
    app.router.add_post("/dashboard/api/broadcast", handle_broadcast_api)
    return app


async def run_dashboard_server():
    app = create_dashboard_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10001)
    await site.start()
