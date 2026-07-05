# EdgeIQ — P1 Data Engineer

## Quick Start

```bash
# 1. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run scrapers (from inside scraper/ folder)
cd scraper
scrapy crawl scaler    -o ../data/scaler.json
scrapy crawl gfg       -o ../data/gfg.json
scrapy crawl udemy     -o ../data/udemy.json
scrapy crawl coursera  -o ../data/coursera.json

# 4. Ingest data to backend (from root edgeiq/ folder)
cd ..
python ingest_data.py

# 5. Verify everything looks right
python verify_data.py

# 6. Emergency backup server (if real backend crashes during demo)
python demo_backup.py
```

## File Structure
```
edgeiq/
├── scraper/
│   └── edgescraper/
│       └── spiders/
│           ├── scaler.py
│           ├── gfg.py
│           ├── udemy.py
│           └── coursera.py
├── data/
│   ├── scaler.json      (mock seed data)
│   ├── gfg.json         (mock seed data)
│   └── mock_all.json    (all 5 companies)
├── ingest_data.py
├── verify_data.py
├── demo_backup.py
├── requirements.txt
└── README.md
```

## JSON Contract with P2 (Backend)
Each scraped item follows this exact shape:
```json
{
  "company": "Scaler",
  "url": "https://www.scaler.com/courses/",
  "scraped_at": "2026-03-25T10:30:00",
  "headline": "Become job-ready in 6 months",
  "subheadlines": ["Live classes", "1:1 Mentorship"],
  "cta_buttons": ["Apply Now", "Book Free Trial"],
  "pricing_text": "₹1,20,000 with EMI options",
  "full_text": "Join Scaler and get placed..."
}
```
