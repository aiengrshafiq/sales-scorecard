# main.py
from fastapi import FastAPI, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, case, extract
from datetime import datetime, timedelta, timezone, date
from collections import Counter
import math
from typing import Optional
from pydantic import BaseModel

from celery_worker import process_pipedrive_event
from database import SessionLocal
from models import PointsLedger, DealStageEvent, PointEventType
import pipedrive_client
import config

app = FastAPI()

# Definitive CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models for new endpoints ---
class User(BaseModel):
    id: int
    name: str

class ActivityDetail(BaseModel):
    id: int
    subject: str
    type: str
    done: bool
    due_date: Optional[date]
    add_time: datetime
    owner_name: str

class WeeklyDealReportItem(BaseModel):
    id: int
    title: str
    owner_name: str
    owner_id: int
    stage_name: str
    value: str
    stage_age_days: int
    is_stuck: bool
    stuck_reason: str
    last_activity_formatted: str
    activities: list[ActivityDetail]


# --- Database Dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Helper Functions ---

# 🛠️ NEW HELPER FUNCTION TO PREVENT TIMEZONE ERRORS
def ensure_timezone_aware(dt: datetime) -> datetime:
    """Ensures a datetime object is timezone-aware, assuming UTC if naive."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

def time_ago(dt: datetime) -> str:
    """Converts a datetime object to a human-readable string like '2h ago'."""
    if not dt: return "N/A"
    now = datetime.now(timezone.utc)
    # Ensure dt is aware before comparison
    dt_aware = ensure_timezone_aware(dt)
    diff = now - dt_aware
    seconds = diff.total_seconds()
    if seconds < 60: return "Just now"
    if seconds < 3600: return f"{int(seconds / 60)}m ago"
    if seconds < 86400: return f"{int(seconds / 3600)}h ago"
    return f"{diff.days}d ago"

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

@app.get("/api/users", response_model=list[User])
def get_sales_users():
    """Endpoint to get a list of sales users for filtering."""
    users = pipedrive_client.get_all_users()
    return [{"id": user["id"], "name": user["name"]} for user in users if user]

@app.get("/api/weekly-report", response_model=list[WeeklyDealReportItem])
def get_weekly_report(user_id: Optional[int] = None):
    """
    Generates a report of deals created in the last 7 days, including
    stage aging, activities, and identifying stuck deals.
    """
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    STUCK_DAYS_THRESHOLD = 5

    params = {
        "status": "open",
        "add_time_since": seven_days_ago.strftime('%Y-%m-%d %H:%M:%S'),
    }
    if user_id:
        params["user_id"] = user_id

    deals = pipedrive_client.get_deals(params)
    if not deals:
        return []

    all_stages = pipedrive_client.get_all_stages()
    stage_map = {stage['id']: stage['name'] for stage in all_stages} if all_stages else {}
    
    report_items = []
    for deal in filter(None, deals):
        activities_raw = pipedrive_client.get_deal_activities(deal["id"])
        activities = []
        last_activity_time = None

        if activities_raw:
            activities_raw.sort(key=lambda x: x.get('add_time', '1970-01-01T00:00:00Z'), reverse=True)
            # ✅ FIX APPLIED HERE
            raw_last_activity_time = datetime.fromisoformat(activities_raw[0]["add_time"].replace('Z', '+00:00'))
            last_activity_time = ensure_timezone_aware(raw_last_activity_time)
            
            for act in activities_raw[:5]:
                 if not all(k in act for k in ['id', 'add_time']): continue
                 # ✅ FIX APPLIED HERE
                 raw_add_time = datetime.fromisoformat(act["add_time"].replace('Z', '+00:00'))
                 add_time = ensure_timezone_aware(raw_add_time)
                 activities.append(ActivityDetail(
                    id=act['id'],
                    subject=act.get('subject', 'No Subject'),
                    type=act.get('type', 'task'),
                    done=act.get('done', False),
                    due_date=act.get('due_date'),
                    add_time=add_time,
                    owner_name=act.get('owner_name', 'Unknown')
                ))

        stage_age_days = 0
        if deal.get("stage_change_time"):
            # ✅ FIX APPLIED HERE - THIS WAS THE LINE CAUSING THE CRASH
            raw_stage_change_time = datetime.fromisoformat(deal["stage_change_time"].replace('Z', '+00:00'))
            stage_change_time = ensure_timezone_aware(raw_stage_change_time)
            stage_age_days = (now - stage_change_time).days

        is_stuck = False
        stuck_reason = ""
        if last_activity_time:
            days_since_activity = (now - last_activity_time).days
            if days_since_activity > STUCK_DAYS_THRESHOLD:
                is_stuck = True
                stuck_reason = f"No activity for {days_since_activity} days."
        elif stage_age_days > STUCK_DAYS_THRESHOLD:
            is_stuck = True
            stuck_reason = f"In stage for {stage_age_days} days with no activities logged."

        owner = deal.get("user_id") or {}
        report_item = WeeklyDealReportItem(
            id=deal["id"],
            title=deal.get("title", "Untitled Deal"),
            owner_name=owner.get("name", "Unknown Owner"),
            owner_id=owner.get("id", 0),
            stage_name=stage_map.get(deal["stage_id"], "Unknown Stage"),
            value=f"{deal.get('currency', '$')} {deal.get('value', 0):,}",
            stage_age_days=stage_age_days,
            is_stuck=is_stuck,
            stuck_reason=stuck_reason,
            last_activity_formatted=time_ago(last_activity_time),
            activities=activities
        )
        report_items.append(report_item)
    return report_items


@app.get("/api/dashboard-data")
def get_dashboard_data(db: Session = Depends(get_db)):
    start_date, end_date, quarter_name = get_current_quarter_dates()

    # --- 1. KPIs ---
    total_points = db.query(func.sum(PointsLedger.points)).filter(PointsLedger.created_at.between(start_date, end_date)).scalar() or 0
    deals_in_pipeline = len(pipedrive_client.get_deals({"status": "open"}))
    
    won_deals_this_quarter = pipedrive_client.get_deals({
        "status": "won",
        "won_date_since": start_date.strftime('%Y-%m-%d')
    })
    # ✅ FIX APPLIED HERE for robust filtering
    won_deals_this_quarter = [
        d for d in won_deals_this_quarter 
        if d and d.get("won_time") and ensure_timezone_aware(datetime.fromisoformat(d["won_time"].replace('Z', '+00:00'))) <= end_date
    ]

    total_days_to_close, deals_for_avg = 0, 0
    for deal in won_deals_this_quarter:
        if deal.get("add_time") and deal.get("won_time"):
            # ✅ FIX APPLIED HERE
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