#!/usr/bin/env python3
"""
Minimal standalone backend for Sirius
No venv needed, just run: python minimal_backend.py
"""

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import uuid
from datetime import datetime

app = FastAPI(title="Sirius Minimal Backend", version="1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage
DATA_STORE = {
    "snapshots": {},  # source_id -> list of snapshots
    "events": [],     # list of all change events
}

WEBHOOK_SECRET = "test"

class WebhookPayload(BaseModel):
    source_id: str
    source_type: str
    data: Dict[str, Any]

class CrawlRequest(BaseModel):
    name: str
    url: str

@app.get("/health")
async def health():
    return {"status": "ok", "service": "Sirius Minimal"}

@app.get("/api/sources")
async def get_sources():
    return {"sources": list(DATA_STORE["snapshots"].keys())}

@app.get("/api/events")
async def get_all_events(limit: int = 100):
    events = sorted(DATA_STORE["events"], key=lambda x: x["created_at"], reverse=True)
    return events[:limit]

@app.get("/api/events/{source_id}")
async def get_events_by_source(source_id: str, limit: int = 50):
    events = [e for e in DATA_STORE["events"] if e["source_id"] == source_id]
    events = sorted(events, key=lambda x: x["created_at"], reverse=True)
    return events[:limit]

@app.post("/webhook/ingest")
async def ingest_webhook(payload: WebhookPayload, x_webhook_secret: str = Header(...)):
    # Verify secret
    if x_webhook_secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")
    
    source_id = payload.source_id
    
    # Initialize storage for this source
    if source_id not in DATA_STORE["snapshots"]:
        DATA_STORE["snapshots"][source_id] = []
    
    # Get previous snapshot
    previous = DATA_STORE["snapshots"][source_id][-1] if DATA_STORE["snapshots"][source_id] else None
    
    # Detect changes
    changes = []
    
    if previous:
        old_data = previous["data"]
        new_data = payload.data
        
        # Price changes
        old_plans = old_data.get("plans", [])
        new_plans = new_data.get("plans", [])
        
        old_by_name = {p.get("name", "").lower(): p for p in old_plans}
        new_by_name = {p.get("name", "").lower(): p for p in new_plans}
        
        for plan_name in set(old_by_name.keys()) | set(new_by_name.keys()):
            old_plan = old_by_name.get(plan_name)
            new_plan = new_by_name.get(plan_name)
            
            if old_plan and not new_plan:
                changes.append({
                    "id": str(uuid.uuid4()),
                    "source_id": source_id,
                    "change_type": "price",
                    "severity": "high",
                    "description": f"Plan '{plan_name}' was removed",
                    "old_value": str(old_plan.get("price")),
                    "new_value": None,
                    "created_at": datetime.now().isoformat(),
                })
            elif not old_plan and new_plan:
                changes.append({
                    "id": str(uuid.uuid4()),
                    "source_id": source_id,
                    "change_type": "price",
                    "severity": "medium",
                    "description": f"New plan '{plan_name}' added at {new_plan.get('price')}",
                    "old_value": None,
                    "new_value": str(new_plan.get("price")),
                    "created_at": datetime.now().isoformat(),
                })
            elif old_plan and new_plan:
                old_price = str(old_plan.get("price", ""))
                new_price = str(new_plan.get("price", ""))
                if old_price != new_price:
                    changes.append({
                        "id": str(uuid.uuid4()),
                        "source_id": source_id,
                        "change_type": "price",
                        "severity": "high",
                        "description": f"Plan '{plan_name}' price changed from {old_price} to {new_price}",
                        "old_value": old_price,
                        "new_value": new_price,
                        "created_at": datetime.now().isoformat(),
                    })
        
        # Headline changes
        old_headline = old_data.get("headline", "")
        new_headline = new_data.get("headline", "")
        if old_headline != new_headline:
            changes.append({
                "id": str(uuid.uuid4()),
                "source_id": source_id,
                "change_type": "messaging",
                "severity": "medium",
                "description": "Primary headline changed",
                "old_value": old_headline,
                "new_value": new_headline,
                "created_at": datetime.now().isoformat(),
            })
        
        # Keyword changes
        old_kw = set(old_data.get("keywords", []))
        new_kw = set(new_data.get("keywords", []))
        added = new_kw - old_kw
        removed = old_kw - new_kw
        
        if added:
            changes.append({
                "id": str(uuid.uuid4()),
                "source_id": source_id,
                "change_type": "keyword",
                "severity": "low",
                "description": f"New keywords: {', '.join(added)}",
                "old_value": None,
                "new_value": ', '.join(added),
                "created_at": datetime.now().isoformat(),
            })
    
    # Store snapshot
    DATA_STORE["snapshots"][source_id].append({
        "id": str(uuid.uuid4()),
        "data": payload.data,
        "created_at": datetime.now().isoformat(),
    })
    
    # Store events
    DATA_STORE["events"].extend(changes)
    
    return {
        "source_id": source_id,
        "snapshot_id": str(uuid.uuid4()),
        "changes_detected": len(changes),
        "events": changes
    }

# Competitor management
COMPETITORS = {}

@app.post("/api/competitors/add")
async def add_competitor(req: CrawlRequest):
    if req.name in COMPETITORS:
        raise HTTPException(status_code=400, detail="Competitor already exists")
    COMPETITORS[req.name] = req.url
    return {"status": "added", "name": req.name, "url": req.url}

@app.get("/api/competitors")
async def list_competitors():
    return {"competitors": COMPETITORS}

@app.delete("/api/competitors/{name}")
async def remove_competitor(name: str):
    if name not in COMPETITORS:
        raise HTTPException(status_code=404, detail="Competitor not found")
    del COMPETITORS[name]
    return {"status": "removed", "name": name}

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Sirius Minimal Backend")
    print("📡 API: http://localhost:8000")
    print("📖 Docs: http://localhost:8000/docs")
    print("")
    uvicorn.run(app, host="0.0.0.0", port=8000)