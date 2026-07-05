# DriftWatch — Market Intelligence Engine

A competitive intelligence platform that actively crawls competitor websites, detects changes in pricing and messaging, and surfaces actionable market insights.

---

## 🎯 What Problem This Solves

Companies struggle to keep track of their competitive landscape. Market intelligence is scattered across:
- Competitor websites and pricing pages
- Review platforms (G2, Trustpilot)
- Social media and forums
- Ad libraries and campaigns

**DriftWatch** automates this intelligence gathering, tracks changes over time, and surfaces the ones that actually matter.

---

## 🚀 Features

### ✅ Implemented

| Feature | Description |
|---------|-------------|
| **🕷️ Active Web Crawler** | Crawls competitor websites and extracts pricing, messaging, keywords |
| **💰 Price Detection** | Tracks pricing changes, new/removed plans, feature changes |
| **🏷️ Keyword Analysis** | Monitors marketing keywords and messaging shifts |
| **📊 Change Detection** | DeepDiff-based comparison with structured event logging |
| **⚠️ Anomaly Detection** | Z-score based price anomaly detection |
| **⏰ Automated Scheduling** | Background crawler runs every 6 hours |
| **🔌 REST API** | Full FastAPI backend with async PostgreSQL |
| **💻 React Frontend** | Real-time dashboard with competitor management |
| **📈 Analytics** | Change summaries, severity tracking, AI insights |

### 🔄 In Progress / Planned

| Feature | Status |
|---------|--------|
| Review Platform Scraping (G2, Trustpilot) | 🔴 Not yet implemented |
| Ad Library Monitoring | 🔴 Not yet implemented |
| Social Media Listening | 🔴 Not yet implemented |
| Advanced NLP for Sentiment Analysis | 🔴 Not yet implemented |
| Whitespace/Trend Analysis | 🟡 Partial (keyword tracking only) |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     REACT FRONTEND                          │
│              (Port 5173 - Vite Dev Server)                  │
│  ┌────────────┐  ┌───────────┐  ┌───────────┐  ┌────────┐ │
│  │ Overview   │  │ Insights  │  │ Changes   │  │ AskAI  │ │
│  │ (Crawler)  │  │ (Events)  │  │ (History) │  │ (Chat) │ │
│  └────────────┘  └───────────┘  └───────────┘  └────────┘ │
└──────────────────────┬────────────────────────────────────┘
                       │ HTTP
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              FASTAPI BACKEND (Port 8000)                    │
│                                                             │
│  ┌──────────────┐  ┌─────────────┐  ┌────────────────┐   │
│  │ Crawler API  │  │ Webhook API │  │ Scheduler      │   │
│  │ /api/crawl/* │  │ /webhook/*  │  │ (APScheduler)  │   │
│  └──────┬───────┘  └──────┬──────┘  └────────┬─────────┘   │
│         │                 │                   │             │
│         ▼                 ▼                   ▼             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Change Detection Engine                 │   │
│  │  • Price change detection                          │   │
│  │  • Keyword change detection                        │   │
│  │  • Messaging/headline detection                    │   │
│  │  • Anomaly detection (Z-score)                     │   │
│  └────────────────────┬────────────────────────────────┘   │
│                       │                                      │
│                       ▼                                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         ASYNC POSTGRESQL DATABASE                   │   │
│  │  • data_snapshots (versioned competitor data)      │   │
│  │  • change_events (detected changes with diff)      │   │
│  │  • price_history (time-series for anomaly detect)  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19, React Router 7, Vite |
| Backend | Python 3.11, FastAPI, Async SQLAlchemy |
| Database | PostgreSQL 15+ (asyncpg) |
| Crawler | aiohttp, BeautifulSoup4, lxml |
| Scheduling | APScheduler (asyncio) |
| Change Detection | DeepDiff, NumPy, SciPy |

---

## 📦 Installation

### Prerequisites
- Python 3.9+
- PostgreSQL 15+
- Node.js 18+

### Windows Setup

```powershell
# Run the automated setup script
.\setup_and_run.ps1

# Or manually:
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your database credentials

cd frontend
npm install
cd ..
```

### Environment Variables

Create a `.env` file:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost/driftwatch_db
WEBHOOK_SECRET=your-webhook-secret-key
PRICE_CHANGE_THRESHOLD_PCT=5.0
ANOMALY_ZSCORE_THRESHOLD=2.5
```

---

## 🚀 Running the Application

### 1. Start Backend

```powershell
.\venv\Scripts\Activate.ps1
cd driftwatch
uvicorn app.main:app --reload --port 8000
```

API docs available at: `http://localhost:8000/docs`

### 2. Start Frontend (new terminal)

```powershell
cd driftwatch\frontend
npm run dev
```

App available at: `http://localhost:5173`

---

## 📡 API Endpoints

### Crawler Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/competitors/add` | Register competitor for auto-crawl |
| GET | `/api/competitors` | List registered competitors |
| DELETE | `/api/competitors/{name}` | Remove competitor |
| POST | `/api/crawl/trigger` | Trigger immediate crawl |
| POST | `/api/crawl/single` | One-time crawl (not scheduled) |

### Data & Events
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sources` | List all data sources |
| GET | `/api/events` | Get all change events |
| GET | `/api/events/{source_id}` | Get events for specific source |
| POST | `/webhook/ingest` | Push data via webhook |

---

## 🎮 Usage Example

### Adding a Competitor via Frontend

1. Go to `http://localhost:5173`
2. Select domain (EdTech, FinTech, etc.)
3. Enter competitor name and URL
4. Click "Add & Analyze Competitor"
5. System crawls, extracts data, and shows results

### Adding via API

```bash
curl -X POST http://localhost:8000/api/competitors/add \
  -H "Content-Type: application/json" \
  -d '{"name": "Byjus", "url": "https://byjus.com/pricing"}'
```

### Triggering Manual Crawl

```bash
curl -X POST http://localhost:8000/api/crawl/trigger
```

---

## 📁 Project Structure

```
driftwatch/
├── app/
│   ├── main.py
│   ├── services/
│   │   ├── crawler.py
│   │   ├── scheduler.py
│   │   ├── change_detector.py
│   │   └── snapshot_service.py
│   ├── db/
│   │   └── database.py
│   └── models/
│       └── models.py
├── frontend/src/
│   ├── App.jsx
│   ├── api.js
│   └── pages/
│       ├── Overview.jsx
│       └── Insights.jsx
├── requirements.txt
└── setup_and_run.ps1
```

---

## 🐛 Known Issues

1. **Crawler limitations**: Some sites with heavy JavaScript may not crawl properly (needs Playwright/Selenium)
2. **No authentication**: Currently no user auth (add JWT for production)
3. **In-memory competitor registry**: Should move to a database table
4. **No tests**: Unit/integration tests not written yet

---

## 🚀 Future Enhancements

- [ ] Review platform scraping (G2, Trustpilot, Capterra)
- [ ] Ad library monitoring (Facebook Ad Library, Google Ads)
- [ ] Social listening (Twitter/X, Reddit, LinkedIn)
- [ ] NLP for sentiment analysis and theme extraction
- [ ] ML-based trend prediction
- [ ] Slack/Teams integration for alerts
- [ ] PDF report generation
- [ ] User authentication and multi-tenancy

---

## 📝 Origin

Originally built as a team hackathon project at SNUC Hacks 2026. Actively developed and extended solo since — including the crawler scheduler, anomaly detection, and dashboard rework.

---

## 📄 License

MIT License
