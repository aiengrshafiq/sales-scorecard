from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo # Requires Python 3.9+

import pipedrive_client

router = APIRouter()

# --- Pydantic Models ---
class DueActivityItem(BaseModel):
    id: int
    subject: str
    type: str
    due_date: str
    owner_name: str
    deal_id: Optional[int]
    deal_title: Optional[str]
    is_overdue: bool

# --- API Endpoint ---
@router.get("/due-activities", response_model=List[DueActivityItem], tags=["Activities"])
async def get_due_activities(
    user_id: Optional[int] = None, 
    start_date: Optional[date] = None, 
    end_date: Optional[date] = None
):
    """
    Fetches all open (not done) activities within a given due_date range (inclusive).
    """
    # ✅ FIXED: Use company timezone for accurate "overdue" checks
    dubai_today = datetime.now(ZoneInfo("Asia/Dubai")).date()

    # Default to one month ago -> today, as per your original request
    if end_date is None:
        end_date = dubai_today
    if start_date is None:
        start_date = dubai_today - timedelta(days: 30)
    
    # ✅ FIXED: Call the new, correct v2 client function
    activities = await pipedrive_client.get_activities_by_due_date_range_async(
        owner_id=user_id,
        start_date=start_date,
        end_date=end_date,
        done=0,
    )

    if not activities:
        return []

    response_items: List[DueActivityItem] = []
    for activity in activities:
        due_date_str = activity.get("due_date")
        if not due_date_str:
            continue
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()

        response_items.append(
            DueActivityItem(
                id=activity["id"],
                subject=activity.get("subject", "No Subject"),
                type=activity.get("type", "task"),
                due_date=due_date_str,
                owner_name=activity.get("owner_name") or (activity.get("owner_id") and str(activity["owner_id"])) or "Unknown",
                deal_id=activity.get("deal_id"),
                deal_title=activity.get("deal_title", "No Associated Deal"),
                is_overdue=(due_date < dubai_today)
            )
        )
        
    return sorted(response_items, key=lambda x: x.due_date)