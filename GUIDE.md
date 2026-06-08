# 🏎️ F1 Career & Manager Game Bot — Complete Beginner Guide
### Zero se deployed bot tak — Step by step in Hinglish

---

## 📋 TABLE OF CONTENTS

1. What is this bot?
2. What you need (requirements)
3. Project folder structure
4. Step 1 — Telegram Bot banana (BotFather)
5. Step 2 — Free database setup (Render PostgreSQL)
6. Step 3 — Free Redis setup (Upstash)
7. Step 4 — Code deploy karna (Render)
8. Step 5 — Bot test karna
9. How to play — Full game guide
10. Admin commands guide
11. Common errors & fixes
12. Local PC par run karna (optional)

---

## 🎮 WHAT IS THIS BOT?

Yeh ek **Formula 1 career + manager game** hai Telegram ke liye.

**Do modes hain:**
- **Driver Career Mode** — Tum ek F1 driver ho. Train karo, team sign karo, race karo, champion bano.
- **Team Manager Mode** — Tum ek team owner ho. Drivers hire karo, car develop karo, league mein compete karo.

**Features:**
- 40+ real + fictional drivers
- Full race simulation (lap by lap events)
- Weather system (rain, safety car, red flag)
- Tyre strategy (soft/medium/hard/wet)
- Research tree (engine, aero, chassis upgrade)
- League system (20 teams compete)
- Sponsor contracts with targets
- Achievement system
- Anti-cheat system
- Admin panel

---

## ⚙️ WHAT YOU NEED

```
✅ Telegram account
✅ GitHub account (free) — code store karne ke liye
✅ Render account (free) — deploy karne ke liye
✅ Upstash account (free) — Redis ke liye
✅ 30-40 minutes
```

**Koi coding knowledge nahi chahiye for deployment!**

---

## 📁 PROJECT FOLDER STRUCTURE

```
f1bot/
├── main.py                    ← Bot start hota hai yahan se
├── requirements.txt           ← Python libraries list
├── Dockerfile                 ← Docker config
├── docker-compose.yml         ← Local development
├── .env.example               ← Environment variables template
├── .env                       ← Tumhara actual config (GitHub par mat daalo!)
│
└── src/
    ├── core/
    │   ├── config.py          ← All settings (budget, race schedule, etc.)
    │   ├── scheduler.py       ← Auto race timer
    │   ├── database/
    │   │   └── session.py     ← PostgreSQL connection
    │   └── cache/
    │       └── redis_client.py ← Redis connection
    │
    ├── models/
    │   └── models.py          ← Database tables (User, Team, Driver, Race...)
    │
    ├── services/
    │   └── game_services.py   ← Game logic (buy driver, run race, etc.)
    │
    ├── simulation/
    │   ├── race_engine.py     ← Race simulation engine
    │   └── driver_db.py       ← All driver data + sponsors + research
    │
    ├── bot/
    │   ├── handlers/
    │   │   ├── main_handlers.py  ← /start /team /race /market etc.
    │   │   └── admin_handlers.py ← /addmoney /ban etc.
    │   ├── keyboards/
    │   │   └── keyboards.py   ← Inline buttons
    │   └── middleware/
    │       ├── auth.py        ← Login check + ban check
    │       ├── anti_cheat.py  ← Rate limiting
    │       └── logging.py     ← Request logging
    │
    └── utils/
        └── logger.py          ← Logging setup
```

---

## STEP 1 — TELEGRAM BOT BANANA 🤖

### 1.1 BotFather se bot banao

1. Telegram par `@BotFather` search karo
2. `/newbot` bhejo
3. Bot ka naam daalo — example: `F1 Racing League Bot`
4. Bot ka username daalo (underscore allowed, must end in 'bot') — example: `f1racing_league_bot`
5. BotFather tumhe ek **TOKEN** dega — yeh save karo!

```
Example token: 7234567890:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

⚠️ **Yeh token kisi ko mat batao!**

### 1.2 Bot commands set karo (optional but nice)

BotFather mein `/setcommands` bhejo, apna bot select karo, phir yeh paste karo:

```
start - Start the bot
register - Create your F1 team
team - View your team
market - Driver transfer market
strategy - Set race strategy
standings - Championship standings
research - Research tree
daily - Daily reward
budget - Budget overview
upgrade - Upgrade car stats
practice - Practice session
leagues - Browse leagues
createleague - Create a league
joinleague - Join a league
help - All commands
```

---

## STEP 2 — FREE POSTGRESQL DATABASE (Render) 🗄️

### 2.1 Render account banao

1. [render.com](https://render.com) par jao
2. "Get Started for Free" — GitHub se sign up karo

### 2.2 PostgreSQL database banao

1. Dashboard mein "New +" button dabao
2. "PostgreSQL" select karo
3. Fill karo:
   - **Name:** `f1bot-db`
   - **Database:** `f1bot`
   - **User:** `f1bot`
   - **Region:** Singapore (ya nearest)
   - **Plan:** Free
4. "Create Database" dabao
5. **Wait 2-3 minutes** for creation

### 2.3 Connection string copy karo

Database page par "Connect" button mein:
- **Internal Database URL** copy karo (agar bot bhi Render par hai)
- **External Database URL** copy karo (agar local test karna hai)

```
Format: postgres://f1bot:PASSWORD@HOST/f1bot

Tum isko change karo:
postgresql+asyncpg://f1bot:PASSWORD@HOST/f1bot
```

⚠️ `postgres://` ko `postgresql+asyncpg://` se replace karo!

---

## STEP 3 — FREE REDIS (Upstash) ⚡

### 3.1 Upstash account banao

1. [upstash.com](https://upstash.com) par jao
2. GitHub se sign up karo

### 3.2 Redis database banao

1. "Create Database" dabao
2. Fill karo:
   - **Name:** `f1bot-redis`
   - **Type:** Regional
   - **Region:** AP-Southeast (Singapore)
3. Create karo

### 3.3 Redis URL copy karo

"Details" tab mein **REDIS_URL** copy karo:
```
Format: rediss://default:PASSWORD@HOST:PORT
```

---

## STEP 4 — CODE DEPLOY KARNA (Render) 🚀

### 4.1 GitHub par code upload karo

1. [github.com](https://github.com) par account banao
2. "New Repository" — naam: `f1bot`
3. Public rakho
4. Saare files upload karo (ya git use karo)

**Git se upload (recommended):**
```bash
git init
git add .
git commit -m "F1 bot initial"
git remote add origin https://github.com/YOURUSERNAME/f1bot.git
git push -u origin main
```

### 4.2 Render par Web Service banao

1. Render dashboard → "New +" → "Web Service"
2. GitHub connect karo → `f1bot` repo select karo
3. Fill karo:
   - **Name:** `f1bot`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python main.py`
   - **Plan:** Free

### 4.3 Environment Variables add karo

"Environment" section mein yeh variables add karo:

| Key | Value |
|-----|-------|
| `BOT_TOKEN` | `7234567890:AAHxxx...` (BotFather wala) |
| `DATABASE_URL` | `postgresql+asyncpg://f1bot:PASS@HOST/f1bot` |
| `REDIS_URL` | `rediss://default:PASS@HOST:PORT` |
| `ADMIN_IDS` | `[YOUR_TELEGRAM_USER_ID]` |
| `LOG_LEVEL` | `INFO` |

**Apna Telegram User ID kaise pata kare?**
- `@userinfobot` Telegram par message karo
- Woh tumhara numeric ID bata dega

### 4.4 Deploy!

"Create Web Service" dabao. Render automatically:
- Code pull karega
- Dependencies install karega
- Bot start karega

**Logs check karo** — agar yeh dikhe toh bot chal raha hai:
```
Starting F1 Management Bot...
Database initialized
Scheduler started
Bot started successfully!
```

### 4.5 Keep-alive (Free tier ke liye important!)

Render free tier 15 minute inactivity par bot band kar deta hai.
Solution — [cron-job.org](https://cron-job.org) par free account banao:

1. New cronjob create karo
2. URL: `https://f1bot.onrender.com/` (tumhara Render URL)
3. Interval: Every 10 minutes
4. Save karo

Ya simply — bot ko webhook mode mein run karo (advanced).

---

## STEP 5 — BOT TEST KARNA ✅

### Basic test flow:

```
1. Bot ko Telegram par dhundho (jo username tune diya)
2. /start bhejo
3. /register bhejo → Team name daalo → logo skip karo
4. /market → Free Agents → /buydriver 1
5. /createleague → League naam daalo → password skip
6. /startseason
7. /strategy → strategy set karo
8. Admin se /forcerace <league_id> karo test ke liye
```

---

## 🎮 HOW TO PLAY — FULL GAME GUIDE

### 🔰 BEGINNER (Day 1)

**Step 1: Register karo**
```
/register
→ Team name type karo (e.g., "Aman Racing")
→ Logo URL optional hai, "skip" type karo
→ Tumhe $100,000,000 milega starting budget!
```

**Step 2: Drivers hire karo**
```
/market
→ "Free Agents" button dabao
→ Driver list dekho (skill, salary sab dikh jayega)
→ /buydriver 1  (driver ID se)
→ Dono drivers hire karo (max 2)
```

**Recommended beginners ke liye:**
- Budget $100M hai
- Salary wale drivers lo jo $3M-$8M/year mein ho
- High "pace" aur "consistency" dekho

**Step 3: League join karo ya banao**
```
/createleague
→ League naam daalo
→ Password — "skip" karo for public
→ Invite code copy karo aur dosto ko bhejo

YA

/joinleague
→ Invite code daalo
```

**Step 4: Season start karo (League owner)**
```
/startseason
→ Minimum 2 teams chahiye
→ 24 races automatically schedule ho jayenge
```

---

### 🏁 RACE WEEKEND

**Practice (optional but useful)**
```
/practice
→ Engineering report milega
→ Example: "Understeer detected. Increase front wing angle."
→ /setup se adjustments karo
```

**Strategy set karo (important!)**
```
/strategy
→ Choose: 1-Stop / 2-Stop / 3-Stop / Aggressive / Balanced / Conservative
→ Starting tyre choose karo: Soft/Medium/Hard
```

**Strategy guide:**
| Strategy | Best for | Risk |
|----------|----------|------|
| Conservative | Beginners, long races | Low |
| Balanced | Normal conditions | Medium |
| Aggressive | Overtaking, catching up | High |
| 1-Stop | Hard tyres, consistent track | Medium |
| 2-Stop | Mixed weather | Low-Medium |
| 3-Stop | Rain/soft tyre circuits | High |

**Race run karna:**
- Auto: Every Sunday 14:00 UTC automatically race hoga
- Manual: Admin `/forcerace <league_id>` kar sakta hai
- Result automatically aayega with lap events!

---

### 💰 ECONOMY GUIDE

**Income sources:**
```
🏆 Race Win: $5,000,000
🥈 P2: $3,000,000
🥉 P3: $2,000,000
📊 P4-P10: $100K - $1.5M
💰 Sponsor bonuses: $1.5M - $50M per race
👑 Season champion prize: $100,000,000
🎁 Daily reward: $500,000
```

**Expenses:**
```
👨‍🏎️ Driver salary: $1.5M - $55M/year
👷 Staff salary: $1M - $12M/year
⬆️ Car upgrades: $3M - $8M per upgrade
🔬 Research: $2.5M - $25M per node
🏭 Facility upgrades: $10M - $100M
```

**Beginner budget tips:**
- Start mein $3M-$5M salary wale drivers lo
- Pehle 5 races mein car upgrades mat karo
- Sponsors zaroor sign karo — free income hai
- Daily reward claim karte raho

---

### ⬆️ CAR DEVELOPMENT GUIDE

**Car stats (1-100):**
```
⚙️ Engine      — Top speed, overtaking
🌬️ Aerodynamics — Cornering, qualifying
🏗️ Chassis     — Overall handling
🔧 Reliability  — DNF chance kam karta hai
🛞 Tyres       — Tyre wear management
🔩 Pit Crew    — Faster pit stops
```

**Upgrade kaise karo:**
```
/upgrade
→ Stat select karo
→ Cost automatically deduct hoga
→ Har upgrade: +3 to stat
```

**Priority order for beginners:**
1. 🔧 Reliability pehle (DNF se bachne ke liye)
2. ⚙️ Engine (overtaking ke liye)
3. 🌬️ Aerodynamics (qualifying ke liye)

**Research tree (better upgrades):**
```
/research
→ Tree select karo (Power Unit / Aero / Weight / Reliability / Tyres)
→ Node select karo
→ RP + Money cost dono chahiye

Research Points kaise milte hain:
- Har Monday: 50 RP automatically
- Wind Tunnel Level 2+: bonus RP
- Simulator Level 2+: bonus RP
```

---

### 🏭 FACILITIES GUIDE

```
/team → Facilities section

Factory       — Overall development speed
Wind Tunnel   — Weekly RP bonus (+5 per level)
Simulator     — Weekly RP bonus (+5 per level)  
HQ            — Reputation boost

Upgrade costs:
Level 1→2: $10,000,000
Level 2→3: $25,000,000
Level 3→4: $50,000,000
Level 4→5: $100,000,000
```

---

### 💼 SPONSORS GUIDE

```
/sponsors

Sponsor tiers:
🟢 Small:   $1.5M-2.2M | Target: Top 15-18
🟡 Medium:  $4.5M-7M   | Target: Top 8-12
🔴 Premium: $12M-20M   | Target: Top 3-5
👑 Title:   $40M-50M   | Target: Points/Win

Tips:
- Premium sponsors ke liye reputation 50+ chahiye
- Agar target miss hoa toh penalty bhi lagta hai
- Small sponsors se shuru karo
```

---

### 👨‍🏎️ DRIVER MARKET GUIDE

**Free agents:**
```
/market → Free Agents
→ List dekho with skills
→ /buydriver <id>
```

**Transfer market:**
```
/selldriver <driver_id> <price>
Example: /selldriver 5 8000000

Auction ke liye:
/selldriver <driver_id> 0 auction
```

**Bidding:**
```
/bid <listing_id> <amount>
Example: /bid 3 12000000
```

**Driver stats explanation:**
```
Pace        — Qualifying speed (high = pole positions)
Racecraft   — Race performance overall
Consistency — Lap time consistency
Wet Weather — Performance in rain
Overtaking  — Passing ability
Defence     — Holding positions
Dev Potential — How much they improve with age
```

---

### 🏆 CHAMPIONSHIP SYSTEM

**Points system (official F1):**
```
P1:  25 pts    P6:  8 pts
P2:  18 pts    P7:  6 pts
P3:  15 pts    P8:  4 pts
P4:  12 pts    P9:  2 pts
P5:  10 pts    P10: 1 pt
```

**Two championships:**
- **Drivers Championship** — Individual driver points
- **Constructors Championship** — Team total (both drivers combined)

**Season end rewards:**
- Constructor champion: $100,000,000 + 20 reputation
- Achievements unlock with bonus money
- New season automatically start hoga

---

### 🎖️ ACHIEVEMENTS

| Achievement | Requirement | Reward |
|-------------|-------------|--------|
| Race Day! | First race complete | $500K + 5 RP |
| Winner! | First race win | $5M + 25 RP |
| Pole Sitter | First pole | $1M + 10 RP |
| On the Podium! | First podium | $2M + 15 RP |
| Century! | 100 championship points | $3M + 20 RP |
| Hat Trick! | 3 wins in a row | $10M + 30 RP |
| Rain Master | Win in heavy rain | $5M + 25 RP |
| CHAMPION! | Win Constructors title | $50M + 100 RP |

---

## 🔧 ADMIN COMMANDS GUIDE

**Pehle admin set karo** — `.env` mein:
```
ADMIN_IDS=[YOUR_TELEGRAM_USER_ID]
```

**Admin commands:**
```
/admin              — Admin panel dekho
/addmoney <team_id> <amount>
                    — Team ko paise do
                    — Example: /addmoney 1 5000000

/removemoney <team_id> <amount>
                    — Team se paise lo

/banplayer <user_id> <reason>
                    — Player ban karo
                    — Example: /banplayer 123456789 cheating

/unbanplayer <user_id>
                    — Ban hatao

/forcerace <league_id>
                    — Race manually trigger karo
                    — Example: /forcerace 1
                    — Use this for testing!

/broadcast <message>
                    — Sab users ko message (future feature)
```

**Team ID kaise pata kare?**
- Database mein jaake teams table dekho
- Ya /team command se — bot team info mein ID show karta hai

---

## ❌ COMMON ERRORS & FIXES

### Error: "Could not connect to database"
```
Fix:
1. DATABASE_URL check karo — postgresql+asyncpg:// se start hona chahiye
2. Render database "running" state mein hai?
3. External URL use karo local testing ke liye
```

### Error: "Redis connection refused"
```
Fix:
1. REDIS_URL check karo
2. Upstash URL "rediss://" se start hota hai (double s = TLS)
3. Free tier mein monthly limit hai — check karo
```

### Error: "Bot token invalid"
```
Fix:
1. BOT_TOKEN exactly copy kiya? Spaces nahi hone chahiye
2. BotFather se naya token lo if needed: /token
```

### Bot respond nahi kar raha
```
Fix:
1. Render logs check karo
2. /forcerace command test karo
3. Anti-cheat: 3 seconds wait karo commands ke beech
4. Render free tier spin-up time: 30-60 seconds pehli baar
```

### "You already have a team" error
```
Fix: Normal hai — ek user sirf ek team bana sakta hai
Different Telegram account se try karo
```

### Race nahi ho rahi automatically
```
Fix:
1. League status "active" hona chahiye (/startseason)
2. Auto race: Sunday 14:00 UTC
3. Test ke liye /forcerace use karo
4. Cron job set kiya? (keep-alive ke liye)
```

---

## 💻 LOCAL PC PAR RUN KARNA (Optional)

### Prerequisites install karo:
```bash
# Python 3.11+
python --version

# Git
git --version
```

### Setup:
```bash
# Clone/download karo
git clone https://github.com/YOURUSERNAME/f1bot.git
cd f1bot

# Virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# .env file banao
cp .env.example .env
# .env file kholo aur values bharo
```

### Docker se run karo (easiest local):
```bash
# Docker Desktop install karo pehle
docker-compose up --build

# Bot chal raha hoga!
# Logs: docker-compose logs -f bot
```

### Bina Docker ke run karo:
```bash
# PostgreSQL aur Redis local install karo pehle
# Ya Render/Upstash ke URLs use karo .env mein

python main.py
```

---

## 📊 DATABASE TABLES REFERENCE

```
users              — Telegram users
teams              — Player teams
leagues            — Competition leagues
drivers            — All drivers (real + fictional)
team_drivers       — Which driver is on which team
staff              — Staff members
team_staff         — Which staff is hired
races              — Race schedule
race_results       — Race outcomes
race_strategies    — Player strategies
qualifying_results — Qualifying grid
seasons            — Season records
driver_standings   — Driver championship table
constructor_standings — Team championship table
driver_transfers   — Transfer market listings
sponsors           — Available sponsors
team_sponsors      — Active sponsor contracts
research_projects  — Completed research
achievements       — Achievement definitions
team_achievements  — Player achievements
admin_logs         — Admin action history
suspicious_activities — Anti-cheat logs
```

---

## 🚀 QUICK START CHECKLIST

```
□ 1. BotFather se bot banaya aur token liya
□ 2. GitHub par code upload kiya
□ 3. Render par PostgreSQL database banaya
□ 4. Upstash par Redis banaya
□ 5. Render par Web Service deploy kiya
□ 6. Environment variables add kiye (BOT_TOKEN, DATABASE_URL, REDIS_URL, ADMIN_IDS)
□ 7. Render logs mein "Bot started successfully" dekha
□ 8. /start bheja aur bot ne respond kiya
□ 9. /register se team banaya
□ 10. /market se driver hire kiya
□ 11. /createleague se league banaya
□ 12. /startseason se season shuru kiya
□ 13. /forcerace se test race chalayi
□ 14. Cron job set kiya keep-alive ke liye
```

---

## 🔗 USEFUL LINKS

| Service | URL | Use |
|---------|-----|-----|
| BotFather | t.me/BotFather | Bot create |
| Render | render.com | Bot + Database host |
| Upstash | upstash.com | Redis |
| Cron-job.org | cron-job.org | Keep-alive |
| UserInfoBot | t.me/userinfobot | Apna Telegram ID |
| GitHub | github.com | Code store |

---

## 💡 TIPS & TRICKS

**Pro tips for beginners:**
1. **Daily reward** bilkul mat bhulo — `/daily` har din
2. **Research points** save karo aur `Power Unit` tree pehle karo
3. **Sponsor contracts** sign karo pehle race se — free income
4. **Reliability** upgrade pehle — DNF se points waste hota hai
5. **2-Stop Balanced** strategy sabse safe hai beginners ke liye
6. **League** mein 8-10 teams ho toh best competition hota hai

**Advanced strategies:**
- Rain mein Intermediate tyres pehle lagao = massive advantage
- Aggressive strategy + fresh soft tyres = overtaking machine
- Title sponsor ke liye reputation 75+ chahiye — grind karo!

---

*Developed for Amanception Community | t.me/AMANCEPTION*
*Guide version 1.0 — F1 Management Game Bot*
