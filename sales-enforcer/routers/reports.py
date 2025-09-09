from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone, date  # ✅ FIXED: Added timedelta and timezone
import asyncio

import pipedrive_client
from utils import ensure_timezone_aware, time_ago

# Create a new router object
router = APIRouter()

# --- Pydantic Models for the report ---
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


# Use the router to declare the path operation
@router.get("/weekly-report", response_model=list[WeeklyDealReportItem], tags=["Reports"])
async def get_weekly_report(user_id: Optional[int] = None):
    """
    Generates a report of deals created in the last 7 days from the "Sales Flow" pipeline.
    """
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    STUCK_DAYS_THRESHOLD = 5
    SALES_FLOW_PIPELINE_ID = 11

    semaphore = asyncio.Semaphore(10)

    params = {
        "status": "open",
        "add_time_since": seven_days_ago.strftime('%Y-%m-%d %H:%M:%S'),
        "pipeline_id": SALES_FLOW_PIPELINE_ID,
    }
    if user_id:
        params["user_id"] = user_id

    deals_task = pipedrive_client.get_deals_async(params)
    stages_task = pipedrive_client.get_all_stages_async()
    deals, all_stages = await asyncio.gather(deals_task, stages_task)

    if not deals:
        return []

    stage_map = {stage['id']: stage['name'] for stage in all_stages} if all_stages else {}

    async def fetch_activities_with_semaphore(deal_id: int):
        async with semaphore:
            return await pipedrive_client.get_deal_activities_async(deal_id)

    activity_tasks = [fetch_activities_with_semaphore(deal["id"]) for deal in deals]
    all_activities_results = await asyncio.gather(*activity_tasks)
    
    report_items = []
    for deal, activities_raw in zip(deals, all_activities_results):
        if not deal: continue

        activities = []
        last_activity_time = None

        if activities_raw:
            activities_raw.sort(key=lambda x: x.get('add_time', '1970-01-01T00:00:00Z'), reverse=True)
            raw_last_activity_time = datetime.fromisoformat(activities_raw[0]["add_time"].replace('Z', '+00:00'))
            last_activity_time = ensure_timezone_aware(raw_last_activity_time)
            
            for act in activities_raw:
                 if not all(k in act for k in ['id', 'add_time']): continue
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
        report_items.append(WeeklyDealReportItem(
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
        ))
    return report_items