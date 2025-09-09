from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta, timezone, date
import asyncio
from collections import Counter

import pipedrive_client
from utils import ensure_timezone_aware, time_ago

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
    activities: List[ActivityDetail]

# ✅ NEW Models for the two-part response structure
class StageSummary(BaseModel):
    stage_name: str
    deal_count: int

class ReportSummary(BaseModel):
    total_deals_created: int
    stage_breakdown: List[StageSummary]

class WeeklyReportResponse(BaseModel):
    summary: ReportSummary
    deals: List[WeeklyDealReportItem]


@router.get("/weekly-report", response_model=WeeklyReportResponse, tags=["Reports"])
async def get_weekly_report(
    user_id: Optional[int] = None, 
    start_date: Optional[date] = None, 
    end_date: Optional[date] = None
):
    now = datetime.now(timezone.utc)
    
    # Default to last 7 days if no dates are provided
    if end_date is None:
        end_date = now.date()
    if start_date is None:
        start_date = end_date - timedelta(days=6)
        
    # Convert dates to timezone-aware datetimes for comparison
    start_datetime = ensure_timezone_aware(datetime.combine(start_date, datetime.min.time()))
    end_datetime = ensure_timezone_aware(datetime.combine(end_date, datetime.max.time()))

    SALES_FLOW_PIPELINE_ID = 11
    
    params = {
        "status": "open",
        "pipeline_id": SALES_FLOW_PIPELINE_ID,
    }
    if user_id:
        params["user_id"] = user_id

    # Fetch all open deals for the pipeline, then we'll filter by date
    all_deals_in_pipeline = await pipedrive_client.get_deals_async(params)
    
    # ✅ Filter deals by creation date (add_time) in Python
    filtered_deals = [
        deal for deal in all_deals_in_pipeline
        if deal and 'add_time' in deal and
        start_datetime <= ensure_timezone_aware(datetime.fromisoformat(deal['add_time'].replace('Z', '+00:00'))) <= end_datetime
    ]

    if not filtered_deals:
        return WeeklyReportResponse(
            summary=ReportSummary(total_deals_created=0, stage_breakdown=[]),
            deals=[]
        )

    stages_task = pipedrive_client.get_all_stages_async()
    all_stages = await stages_task
    stage_map = {stage['id']: stage['name'] for stage in all_stages} if all_stages else {}

    # --- Section 1: Generate Summary ---
    stage_ids = [deal['stage_id'] for deal in filtered_deals]
    stage_counts = Counter(stage_ids)
    stage_breakdown = [
        StageSummary(stage_name=stage_map.get(stage_id, f"Unknown Stage {stage_id}"), deal_count=count)
        for stage_id, count in stage_counts.items()
    ]
    summary = ReportSummary(
        total_deals_created=len(filtered_deals),
        stage_breakdown=sorted(stage_breakdown, key=lambda x: x.deal_count, reverse=True)
    )

    # --- Section 2: Generate Detailed Deal List ---
    semaphore = asyncio.Semaphore(10)
    async def fetch_activities_with_semaphore(deal_id: int):
        async with semaphore:
            return await pipedrive_client.get_deal_activities_async(deal_id)

    activity_tasks = [fetch_activities_with_semaphore(deal["id"]) for deal in filtered_deals]
    all_activities_results = await asyncio.gather(*activity_tasks)
    
    detailed_deals = []
    STUCK_DAYS_THRESHOLD = 5
    for deal, activities_raw in zip(filtered_deals, all_activities_results):
        # ... (The detailed processing logic is the same as before) ...
        activities = []
        last_activity_time = None
        if activities_raw:
            activities_raw.sort(key=lambda x: x.get('add_time', '1970-01-01T00:00:00Z'), reverse=True)
            last_activity_time = ensure_timezone_aware(datetime.fromisoformat(activities_raw[0]["add_time"].replace('Z', '+00:00')))
            for act in activities_raw:
                 if not all(k in act for k in ['id', 'add_time']): continue
                 add_time = ensure_timezone_aware(datetime.fromisoformat(act["add_time"].replace('Z', '+00:00')))
                 activities.append(ActivityDetail(id=act['id'], subject=act.get('subject', 'No Subject'), type=act.get('type', 'task'), done=act.get('done', False), due_date=act.get('due_date'), add_time=add_time, owner_name=act.get('owner_name', 'Unknown')))
        
        stage_age_days = 0
        if deal.get("stage_change_time"):
            stage_change_time = ensure_timezone_aware(datetime.fromisoformat(deal["stage_change_time"].replace('Z', '+00:00')))
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
        detailed_deals.append(WeeklyDealReportItem(id=deal["id"], title=deal.get("title", "Untitled Deal"), owner_name=owner.get("name", "Unknown Owner"), owner_id=owner.get("id", 0), stage_name=stage_map.get(deal["stage_id"], "Unknown Stage"), value=f"{deal.get('currency', '$')} {deal.get('value', 0):,}", stage_age_days=stage_age_days, is_stuck=is_stuck, stuck_reason=stuck_reason, last_activity_formatted=time_ago(last_activity_time), activities=activities))

    return WeeklyReportResponse(summary=summary, deals=detailed_deals)