# Sirius Market Intelligence Engine

A production-ready competitor intelligence platform that actively crawls competitor websites, detects changes in pricing/messaging, and provides actionable market insights.

Built for **SNUC Hacks 2026 - Track 2: Market Intelligence**

## 🎯 What Problem This Solves

Companies struggle to understand their competitive landscape. Market intelligence is scattered across:
- Competitor websites and pricing pages
- Review platforms (G2, Trustpilot)
- Social media and forums
- Ad libraries and campaigns

**Sirius** automates this intelligence gathering, tracks changes over time, and surfaces actionable insights.

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

Create `.env` file:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost/sirius_db
WEBHOOK_SECRET=your-webhook-secret-key
PRICE_CHANGE_THRESHOLD_PCT=5.0
ANOMALY_ZSCORE_THRESHOLD=2.5
```

---

## 🚀 Running the Application

### 1. Start Backend

```powershell
.\venv\Scripts\Activate.ps1
cd sirius-main
uvicorn app.main:app --reload --port 8000
```

API docs available at: `http://localhost:8000/docs`

### 2. Start Frontend (new terminal)

```powershell
cd sirius-main\frontend
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

## 📊 Track 2 Compliance Analysis

| Requirement | Implementation | Gap |
|-------------|----------------|-----|
| **Crawl competitor websites** | ✅ Active crawler with aiohttp + BeautifulSoup | None |
| **Track pricing changes** | ✅ Price detection with history & anomaly | None |
| **Monitor review platforms** | 🔴 Not implemented | Needs G2/Trustpilot scrapers |
| **Ad library tracking** | 🔴 Not implemented | Needs Facebook/Google Ads API |
| **Influencer/community mentions** | 🔴 Not implemented | Needs Reddit/forum scrapers |
| **Trend/whitespace analysis** | 🟡 Basic keyword tracking | Needs NLP clustering |
| **Decision-ready insights** | 🟡 Event summaries | Needs AI-generated reports |

---

## 🔧 Key Files Added/Modified

```
sirius-main/
├── app/
│   ├── main.py                    # ← Added crawler endpoints + scheduler
│   ├── services/
│   │   ├── crawler.py             # ← NEW: Web crawler
│   │   ├── scheduler.py           # ← NEW: APScheduler integration
│   │   ├── change_detector.py     # Existing: Detection logic
│   │   └── snapshot_service.py    # Existing: Data processing
│   ├── db/
│   │   └── database.py            # ← Added async_session export
│   └── models/
│       └── models.py              # Existing: Database schemas
├── frontend/src/
│   ├── App.jsx                    # ← Fixed: Removed broken code
│   ├── api.js                     # ← Added: Crawler API methods
│   └── pages/
│       ├── Overview.jsx           # ← Enhanced: Competitor management
│       └── Insights.jsx           # ← NEW: Event dashboard
├── requirements.txt               # ← Added: beautifulsoup4, aiohttp
├── setup_and_run.ps1             # ← NEW: Automated setup
└── README.md                      # ← NEW: This file
```

---

## 🐛 Known Issues

1. **Crawler limitations**: Some sites with heavy JavaScript may not crawl properly (needs Playwright/Selenium)
2. **No authentication**: Currently no user auth (add JWT for production)
3. **In-memory competitor registry**: Should move to database table
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

## 👥 Team

**Sirius** - SNUC Hacks 2026

---

## 📄 License

MIT License - Built for educational purposes
