from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date, timezone, timedelta

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
    Fetches all open (not done) activities within a given date range.
    """
    now_date = datetime.now(timezone.utc).date()

    # Default date range if none are provided
    if start_date is None:
        start_date = now_date
    if end_date is None:
        end_date = now_date + timedelta(days: 30)
    
    # ✅ FIXED: Call the correct client function that fetches activities with date filters.
    activities = await pipedrive_client.get_activities_by_date_range_async(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date
    )

    if not activities:
        return []

    # Process the filtered activities into the response model
    response_items = []
    for activity in activities:
        if not activity.get("due_date"): continue
        
        due_date = datetime.strptime(activity["due_date"], '%Y-%m-%d').date()
        
        response_items.append(
            DueActivityItem(
                id=activity["id"],
                subject=activity.get("subject", "No Subject"),
                type=activity.get("type", "task"),
                due_date=activity["due_date"],
                owner_name=activity.get("owner_name", "Unknown"),
                deal_id=activity.get("deal_id"),
                deal_title=activity.get("deal_title", "No Associated Deal"),
                is_overdue=(due_date < now_date)
            )
        )
        
    return sorted(response_items, key=lambda x: x.due_date)