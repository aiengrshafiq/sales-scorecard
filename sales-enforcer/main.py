# main.py
from fastapi import FastAPI, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from celery_worker import process_pipedrive_event
from database import SessionLocal
from models import PointsLedger, DealStageEvent
import pipedrive_client
import config

app = FastAPI()

# --- CORS Configuration ---
# This allows your Next.js dashboard to communicate with this API
origins = [
    "https://delightful-ocean-0f9808600.1.azurestaticapps.net", # Your frontend URL
    "http://localhost:3000", # For local development
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Database Dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- API Endpoints ---
@app.get("/")
def read_root():
    return {"status": "Sales Enforcer is running!"}

@app.post("/webhook/pipedrive")
async def pipedrive_webhook(request: Request):
    payload = await request.json()
    process_pipedrive_event.delay(payload)
    return Response(status_code=200)

@app.get("/api/dashboard-data")
def get_dashboard_data(db: Session = Depends(get_db)):
    """
    This single endpoint provides all the data needed for the dashboard.
    """
    # 1. KPIs
    total_points = db.query(func.sum(PointsLedger.points)).scalar() or 0
    deals_in_pipeline = db.query(func.count(DealStageEvent.deal_id.distinct())).scalar() or 0
    
    # 2. Leaderboard
    leaderboard_query = (
        db.query(
            PointsLedger.user_id,
            func.sum(PointsLedger.points).label("total_score")
        )
        .group_by(PointsLedger.user_id)
        .order_by(desc("total_score"))
        .limit(5)
        .all()
    )
    
    leaderboard = []
    for row in leaderboard_query:
        user_info = pipedrive_client.get_user(row.user_id)
        leaderboard.append({
            "id": row.user_id,
            "name": user_info.get("name", f"User {row.user_id}"),
            "avatar": user_info.get("icon_url", f"https://i.pravatar.cc/150?u={row.user_id}"),
            "points": row.total_score,
            "dealsWon": 0, # Placeholder, can be calculated with more queries
            "onStreak": False, # Placeholder
        })

    # 3. Points Over Time (example for last 7 days)
    # A real implementation would group by week/month
    points_over_time = [
        {"week": "W1", "points": 400}, {"week": "W2", "points": 650},
        {"week": "W3", "points": 500}, {"week": "W4", "points": 800},
    ]

    # 4. Recent Activity
    recent_activity_query = db.query(PointsLedger).order_by(desc(PointsLedger.created_at)).limit(5).all()
    recent_activity = [{
        "id": entry.id,
        "type": "stage", # Simplified for now
        "text": entry.notes,
        "time": "Just now" # Placeholder
    } for entry in recent_activity_query]

    # Combine all data into a single response object
    dashboard_data = {
        "kpis": {
            "totalPoints": total_points,
            "quarterlyTarget": 15000, # From config or DB
            "dealsInPipeline": deals_in_pipeline,
            "avgSpeedToClose": 18, # Placeholder
        },
        "leaderboard": leaderboard,
        "pointsOverTime": points_over_time,
        "recentActivity": recent_activity,
        # Other data like salesHealth can be added here
        "salesHealth": {
            "leadToContactedSameDay": 82, "qualToDesignFee": 65,
            "designFeeCompliance": 95, "proposalToClose": 40,
            "topLossReasons": [{"reason": 'Budget', "value": 45}, {"reason": 'Timing', "value": 30}],
        },
    }

    return dashboard_data
