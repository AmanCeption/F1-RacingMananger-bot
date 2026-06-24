# 🏎️ F1 Racing Manager Bot

A fully-featured Telegram Formula 1 Management Simulator built with Python and Aiogram.

Create your own F1 team, sign drivers, hire staff, develop your car, compete in leagues, and fight for World Championships through realistic race simulations.

---

## 🚀 Features

### 👤 User System
- Telegram account integration
- User profiles
- Daily rewards
- Progress tracking
- Anti-cheat protection

### 🏁 Team Management
- Create and customize your own F1 team
- Manage team budget
- Team reputation system
- Research & Development progression
- Team achievements

### 👨‍✈️ Driver Market
- Sign real and fictional drivers
- Driver transfers
- Driver ratings and performance stats
- Contract management

### 👨‍🔧 Staff Management
- Hire technical staff
- Team Principals
- Race Engineers
- Technical Directors
- Strategy Specialists
- Performance bonuses from staff

### 🏆 League System
- Create private leagues
- Public leagues
- Invite code support
- Password-protected championships
- Multi-season progression

### 🏎️ Race Weekend Simulation
- Practice sessions
- Qualifying simulation
- Dynamic weather
- Race strategies
- Pit stop management
- Realistic race engine

### 📊 Championship System
- Driver Standings
- Constructor Standings
- Season progression
- Historical records

### 🔬 Research & Development
- Spend Research Points
- Unlock upgrades
- Improve team performance
- Long-term progression system

### 💰 Sponsors
- Sponsor contracts
- Financial rewards
- Team funding management

### 🛡️ Admin Tools
- Admin dashboard
- User moderation
- Logs and analytics
- League management
- Anti-cheat monitoring

---

## 🏗️ Tech Stack

- Python 3.11+
- Aiogram 3
- PostgreSQL
- SQLAlchemy
- Redis
- APScheduler
- Docker
- AioHTTP

---

## 📂 Project Structure

```
src/
├── admin/
├── bot/
│   ├── handlers/
│   ├── keyboards/
│   ├── middleware/
│   └── filters/
├── core/
│   ├── database/
│   ├── cache/
│   └── scheduler.py
├── models/
├── services/
├── simulation/
└── utils/
```

---

## ⚙️ Installation

### Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/F1Game-bot.git
cd F1Game-bot
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure Environment

Copy:

```bash
.env.example
```

to:

```bash
.env
```

Then configure:

```env
BOT_TOKEN=YOUR_BOT_TOKEN
DATABASE_URL=YOUR_DATABASE_URL
REDIS_URL=YOUR_REDIS_URL
ADMIN_IDS=[YOUR_TELEGRAM_ID]
```

---

## ▶️ Running Locally

```bash
python main.py
```

---

## 🐳 Docker Deployment

```bash
docker-compose up --build
```

---

## 🌐 Deployment

Supported Platforms:

- Render
- Railway
- VPS
- Docker
- Self Hosted Linux Server

---

## 🎮 Gameplay Overview

1. Create your F1 Team
2. Join or create a League
3. Sign Drivers and Staff
4. Develop your Car
5. Earn Research Points
6. Set Race Strategies
7. Compete in Championships
8. Win the Driver and Constructor Titles

---

## 📈 Planned Features

- Driver Academy
- Engine Suppliers
- Team Liveries
- Sponsorship Negotiations
- Driver Contracts
- Live Race Commentary
- Multiplayer Events
- Hall of Fame

---

## 🤝 Contributing

Pull Requests and suggestions are welcome.

If you find bugs or have ideas for improvements, open an issue.

---

## 📜 License

This project is released under the MIT License.

---

## 👨‍💻 Developed By

**AmanCeption**

Telegram: https://t.me/AmanCeption

Built for Formula 1 fans who dream of running their own championship-winning team. 🏆🏎️
