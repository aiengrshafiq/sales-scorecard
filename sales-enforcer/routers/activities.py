from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date, timezone, timedelta
from zoneinfo import ZoneInfo

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
    Fetches all open (not done) activities and then filters them by due date range.
    """
    # ✅ FIXED: First, fetch ALL open activities for the user.
    all_open_activities = await pipedrive_client.get_all_open_activities_async(user_id=user_id)

    # Use company TZ (assumed Dubai) for date comparisons
    dubai_today = datetime.now(ZoneInfo("Asia/Dubai")).date()

    # Default to one month ago -> today
    if end_date is None:
        end_date = dubai_today
    if start_date is None:
        start_date = dubai_today - timedelta(days=30)

    # ✅ FIXED: Now, filter the complete list by the correct due date.
    filtered_activities = []
    for activity in all_open_activities:
        if not (activity and activity.get("due_date")):
            continue
        
        try:
            due_date = datetime.strptime(activity["due_date"], '%Y-%m-%d').date()
            if start_date <= due_date <= end_date:
                filtered_activities.append(activity)
        except (ValueError, TypeError):
            continue # Skip if date is malformed

    if not filtered_activities:
        return []

    response_items: List[DueActivityItem] = []
    for activity in filtered_activities:
        due_date = datetime.strptime(activity["due_date"], "%Y-%m-%d").date()

        response_items.append(
            DueActivityItem(
                id=activity["id"],
                subject=activity.get("subject", "No Subject"),
                type=activity.get("type", "task"),
                due_date=activity["due_date"],
                owner_name=activity.get("owner_name") or "Unknown",
                deal_id=activity.get("deal_id"),
                deal_title=activity.get("deal_title", "No Associated Deal"),
                is_overdue=(due_date < dubai_today),
            )
        )
        
    return sorted(response_items, key=lambda x: x.due_date)