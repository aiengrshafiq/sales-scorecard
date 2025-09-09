from fastapi import FastAPI, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, case, extract
from datetime import datetime, timedelta, timezone, date
from collections import Counter
import math
from pydantic import BaseModel
import asyncio

from celery_worker import process_pipedrive_event
from database import SessionLocal
from models import PointsLedger, DealStageEvent, PointEventType
import pipedrive_client
import config
from routers import reports as reports_router
from utils import ensure_timezone_aware, time_ago # ✅ CHANGED: Import from utils.py

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(reports_router.router, prefix="/api")

# --- Pydantic Models ---
class User(BaseModel):
    id: int
    name: str

# --- Database Dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Helper Functions ---
# ✅ REMOVED: `ensure_timezone_aware` and `time_ago` are now in utils.py

def get_current_quarter_dates():
    now = datetime.now(timezone.utc)
    current_quarter = math.ceil(now.month / 3)
    start_month = 3 * current_quarter - 2
    end_month = 3 * current_quarter
    start_date = datetime(now.year, start_month, 1, tzinfo=timezone.utc)
    
    next_month_start_year = now.year
    next_month_start_month = end_month + 1
    if next_month_start_month > 12:
        next_month_start_month = 1
        next_month_start_year += 1
        
    next_month_start = datetime(next_month_start_year, next_month_start_month, 1, tzinfo=timezone.utc)
    end_date = next_month_start - timedelta(days=1)
    
    quarter_name = f"Q{current_quarter} {now.year}"
    return start_date, end_date.replace(hour=23, minute=59, second=59), quarter_name

# --- API Endpoints ---
@app.get("/")
def read_root():
    return {"status": "Sales Enforcer is running!"}

@app.post("/webhook/pipedrive")
async def pipedrive_webhook(request: Request):
    payload = await request.json()
    process_pipedrive_event.delay(payload)
    return Response(status_code=200)

@app.get("/api/users", response_model=list[User], tags=["Users"])
async def get_sales_users():
    users = await pipedrive_client.get_all_users_async()
    return [{"id": user["id"], "name": user["name"]} for user in users if user]


@app.get("/api/dashboard-data", tags=["Dashboard"])
def get_dashboard_data(db: Session = Depends(get_db)):
    start_date, end_date, quarter_name = get_current_quarter_dates()

    # --- 1. KPIs ---
    total_points = db.query(func.sum(PointsLedger.points)).filter(PointsLedger.created_at.between(start_date, end_date)).scalar() or 0
    deals_in_pipeline = len(pipedrive_client.get_deals({"status": "open"}))
    
    won_deals_this_quarter = pipedrive_client.get_deals({
        "status": "won",
        "won_date_since": start_date.strftime('%Y-%m-%d')
    })
    won_deals_this_quarter = [
        d for d in won_deals_this_quarter 
        if d and d.get("won_time") and ensure_timezone_aware(datetime.fromisoformat(d["won_time"].replace('Z', '+00:00'))) <= end_date
    ]

    total_days_to_close, deals_for_avg = 0, 0
    for deal in won_deals_this_quarter:
        if deal.get("add_time") and deal.get("won_time"):
            add_time = ensure_timezone_aware(datetime.fromisoformat(deal["add_time"].replace('Z', '+00:00')))
            won_time = ensure_timezone_aware(datetime.fromisoformat(deal["won_time"].replace('Z', '+00:00')))
            total_days_to_close += (won_time - add_time).days
            deals_for_avg += 1
    avg_speed_to_close = round(total_days_to_close / deals_for_avg, 1) if deals_for_avg > 0 else 0

    # --- 2. Leaderboard ---
    leaderboard_query = (
        db.query(
            PointsLedger.user_id,
            func.sum(PointsLedger.points).label("total_score"),
            func.count(case((PointsLedger.notes == "Deal WON", PointsLedger.deal_id), else_=None).distinct()).label("deals_won")
        )
        .filter(PointsLedger.created_at.between(start_date, end_date))
        .group_by(PointsLedger.user_id)
        .order_by(desc("total_score"))
        .limit(5)
        .all()
    )
    leaderboard = []
    for row in leaderboard_query:
        user_info = pipedrive_client.get_user(row.user_id)
        leaderboard.append({
            "id": row.user_id, "name": user_info.get("name", f"User {row.user_id}"),
            "avatar": user_info.get("icon_url", f"https://i.pravatar.cc/150?u={row.user_id}"),
            "points": int(row.total_score or 0), "dealsWon": row.deals_won, "onStreak": False,
        })

    # --- 3. Points Over Time ---
    points_by_week = db.query(
        extract('week', PointsLedger.created_at).label('week_number'),
        func.sum(PointsLedger.points).label('total_points')
    ).filter(PointsLedger.created_at >= datetime.now(timezone.utc) - timedelta(weeks=12)).group_by('week_number').order_by('week_number').all()
    points_over_time = [{"week": f"W{int(r.week_number)}", "points": r.total_points} for r in points_by_week]

    # --- 4. Recent Activity ---
    recent_events = db.query(PointsLedger).order_by(desc(PointsLedger.created_at)).limit(5).all()
    type_map = {PointEventType.BONUS: "bonus", PointEventType.STAGE_ADVANCE: "stage"}
    recent_activity = [{"id": entry.id, "type": "win" if entry.notes and "won" in entry.notes.lower() else type_map.get(entry.event_type, "stage"), "text": entry.notes, "time": time_ago(entry.created_at) } for entry in recent_events]

    # --- 5. Sales Health ---
    qual_stage_id, proposal_stage_id = 91, 94
    deals_reached_qual = set(r[0] for r in db.query(DealStageEvent.deal_id).filter(DealStageEvent.stage_id == qual_stage_id).all())
    deals_reached_proposal = set(r[0] for r in db.query(DealStageEvent.deal_id).filter(DealStageEvent.stage_id == proposal_stage_id).all())
    
    qual_to_proposal_conversion = int((len(deals_reached_qual.intersection(deals_reached_proposal)) / len(deals_reached_qual)) * 100) if deals_reached_qual else 0

    deals_won_ids = set(r[0] for r in db.query(PointsLedger.deal_id).filter(PointsLedger.notes == "Deal WON").all())
    proposal_to_close_conversion = int((len(deals_reached_proposal.intersection(deals_won_ids)) / len(deals_reached_proposal)) * 100) if deals_reached_proposal else 0

    lost_deals = pipedrive_client.get_deals({"status": "lost", "limit": 250})
    loss_key = config.DASHBOARD_CONFIG["field_keys"]["loss_reason"]
    reasons = [deal.get(loss_key) for deal in lost_deals if deal and deal.get(loss_key)]
    top_loss_reasons = [{"reason": r, "value": int((c / len(reasons)) * 100)} for r, c in Counter(reasons).most_common(3)] if reasons else []

    dashboard_data = {
        "kpis": { "totalPoints": int(total_points), "quarterlyTarget": config.DASHBOARD_CONFIG["quarterly_points_target"], "dealsInPipeline": deals_in_pipeline, "avgSpeedToClose": avg_speed_to_close, "quarterName": quarter_name },
        "leaderboard": leaderboard, "pointsOverTime": points_over_time, "recentActivity": recent_activity,
        "salesHealth": { "leadToContactedSameDay": 82, "qualToDesignFee": qual_to_proposal_conversion, "designFeeCompliance": 95, "proposalToClose": proposal_to_close_conversion, "topLossReasons": top_loss_reasons, },
    }
    return dashboard_data