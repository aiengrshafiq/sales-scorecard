from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta, timezone, date
import asyncio
from collections import Counter

import pipedrive_client
from utils import ensure_timezone_aware, time_ago

router = APIRouter()

# --- Pydantic Models (Unchanged) ---
class ActivityDetail(BaseModel):id:int;subject:str;type:str;done:bool;due_date:Optional[date];add_time:datetime;owner_name:str
class WeeklyDealReportItem(BaseModel):id:int;title:str;owner_name:str;owner_id:int;unique_id:Optional[str]=None;stage_name:str;value:str;stage_age_days:int;is_stuck:bool;stuck_reason:str;last_activity_formatted:str;activities:List[ActivityDetail]
class StageSummary(BaseModel):stage_name:str;deal_count:int
class ReportSummary(BaseModel):total_deals_created:int;stage_breakdown:List[StageSummary]
class WeeklyReportResponse(BaseModel):summary:ReportSummary;deals:List[WeeklyDealReportItem]

@router.get("/weekly-report", response_model=WeeklyReportResponse, tags=["Reports"])
async def get_weekly_report(
    user_id: Optional[int] = None, 
    start_date: Optional[date] = None, 
    end_date: Optional[date] = None
):
    now = datetime.now(timezone.utc)
    
    if end_date is None: end_date = now.date()
    if start_date is None: start_date = end_date - timedelta(days=6)
        
    start_datetime = ensure_timezone_aware(datetime.combine(start_date, datetime.min.time()))
    end_datetime = ensure_timezone_aware(datetime.combine(end_date, datetime.max.time()))

    SALES_FLOW_PIPELINE_ID = 11
    DEAL_UNIQUE_ID_KEY = "8d5a64af5474d18b62fb4d6e2881fb65009fca99"
    
    # ✅ FIXED: Call the main /deals endpoint with the correct pipeline_id and sort order.
    # This is the most efficient way to get the data we need.
    params = { 
        "status": "open", 
        "pipeline_id": SALES_FLOW_PIPELINE_ID,
        "sort": "add_time DESC" # Ask for newest deals first
    }
    if user_id: params["user_id"] = user_id

    all_deals_in_pipeline = await pipedrive_client.get_deals_async(params)
    
    # ✅ FIXED: Now we just filter this correctly-scoped list by date.
    # We can stop checking as soon as we find a deal older than our start_date.
    filtered_deals = []
    for deal in all_deals_in_pipeline:
        if not (deal and 'add_time' in deal): continue
        
        add_time = ensure_timezone_aware(datetime.fromisoformat(deal['add_time'].replace('Z', '+00:00')))
        
        if add_time < start_datetime:
            # Since the list is sorted by newest, we can stop here.
            break
        
        if add_time <= end_datetime:
            filtered_deals.append(deal)

    if not filtered_deals:
        return WeeklyReportResponse(summary=ReportSummary(total_deals_created=0, stage_breakdown=[]), deals=[])

    all_stages = await pipedrive_client.get_all_stages_async()
    stage_map = {stage['id']: stage['name'] for stage in all_stages} if all_stages else {}

    # --- Section 1: Generate Summary ---
    stage_ids = [deal['stage_id'] for deal in filtered_deals]
    stage_counts = Counter(stage_ids)
    stage_breakdown = [StageSummary(stage_name=stage_map.get(sid, f"Unknown Stage {sid}"), deal_count=c) for sid, c in stage_counts.items()]
    summary = ReportSummary(total_deals_created=len(filtered_deals), stage_breakdown=sorted(stage_breakdown, key=lambda x: x.deal_count, reverse=True))

    # --- Section 2: Generate Detailed Deal List ---
    semaphore = asyncio.Semaphore(10)
    async def fetch_full_data(deal_id: int):
        async with semaphore:
            # Fetch full deal details and activities concurrently for accuracy
            deal_task = pipedrive_client.get_deal_async(deal_id)
            activity_task = pipedrive_client.get_deal_activities_async(deal_id)
            return await asyncio.gather(deal_task, activity_task)

    tasks = [fetch_full_data(deal["id"]) for deal in filtered_deals]
    results = await asyncio.gather(*tasks)
    
    detailed_deals = []
    STUCK_DAYS_THRESHOLD = 5
    for deal, activities_raw in results:
        if not deal: continue # Skip if fetching full deal details failed
        
        activities = []
        if activities_raw:
            activities_raw.sort(key=lambda x: x.get('add_time', '1970-01-01T00:00:00Z'), reverse=True)
            for act in activities_raw:
                 if not all(k in act for k in ['id', 'add_time']): continue
                 add_time = ensure_timezone_aware(datetime.fromisoformat(act["add_time"].replace('Z', '+00:00')))
                 activities.append(ActivityDetail(id=act['id'], subject=act.get('subject', 'No Subject'), type=act.get('type', 'task'), done=act.get('done', False), due_date=act.get('due_date'), add_time=add_time, owner_name=act.get('owner_name', 'Unknown')))
        
        last_activity_time = None
        if deal.get("last_activity_date"):
            last_activity_time = ensure_timezone_aware(datetime.strptime(deal["last_activity_date"], '%Y-%m-%d'))
        
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
            stuck_reason = f"In stage for {stage_age_days} days with no completed activities."

        owner = deal.get("user_id") or {}
        detailed_deals.append(WeeklyDealReportItem(
            id=deal["id"],
            title=deal.get("title", "Untitled Deal"),
            owner_name=owner.get("name", "Unknown Owner"),
            owner_id=owner.get("id", 0),
            unique_id=deal.get(DEAL_UNIQUE_ID_KEY),
            stage_name=stage_map.get(deal["stage_id"], "Unknown Stage"),
            value=f"{deal.get('currency', '$')} {deal.get('value', 0):,}",
            stage_age_days=stage_age_days,
            is_stuck=is_stuck,
            stuck_reason=stuck_reason,
            last_activity_formatted=time_ago(last_activity_time),
            activities=activities
        ))
    
    return WeeklyReportResponse(summary=summary, deals=detailed_deals)