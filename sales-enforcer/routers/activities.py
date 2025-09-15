from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo # Requires Python 3.9+
import asyncio

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
    Fetch open (not done) activities whose due_date is within [start_date, end_date], inclusive.
    """
    tz = ZoneInfo("Asia/Dubai")
    today_dubai = datetime.now(tz).date()

    # Default to one month ago -> today
    if end_date is None:
        end_date = today_dubai
    if start_date is None:
        start_date = today_dubai - timedelta(days=30)

    # ✅ FIXED: Use the correct logic to either fetch for one user or aggregate for all.
    if user_id:
        activities = await pipedrive_client.get_activities_by_due_date_range_v2_async(
            owner_id=user_id,
            start_date=start_date,
            end_date=end_date,
            done=False,
        )
    else:
        activities = await pipedrive_client.get_due_activities_all_salespersons_async(
            start_date=start_date,
            end_date=end_date,
            done=False,
        )

    if not activities:
        return []

    response_items: List[DueActivityItem] = []
    for activity in activities:
        due_date_str = activity.get("due_date")
        if not due_date_str: continue
        
        due_date = date.fromisoformat(due_date_str)

        response_items.append(
            DueActivityItem(
                id=activity["id"],
                subject=activity.get("subject") or "No Subject",
                type=activity.get("type") or "task",
                due_date=due_date_str,
                owner_name=activity.get("owner_name") or str(activity.get("owner_id") or "Unknown"),
                deal_id=activity.get("deal_id"),
                deal_title=activity.get("deal_title") or "No Associated Deal",
                is_overdue=(due_date < today_dubai),
            )
        )
        
    return sorted(response_items, key=lambda x: x.due_date)