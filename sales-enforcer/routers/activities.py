from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
# ✅ FIXED: Added missing timezone and timedelta imports
from datetime import datetime, date, timezone, timedelta

import pipedrive_client

router = APIRouter()

# --- Pydantic Models for the new endpoint ---
class DueActivityItem(BaseModel):
    id: int
    subject: str
    type: str
    due_date: str # Send as string for simplicity
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
    all_open_activities = await pipedrive_client.get_all_open_activities_async(user_id=user_id)

    now_date = datetime.now(timezone.utc).date()
    # Default date range if none are provided
    start_date_filter = start_date if start_date else now_date
    end_date_filter = end_date if end_date else now_date + timedelta(days=30)

    # Filter activities in Python to match the date range
    filtered_activities = []
    for activity in all_open_activities:
        if not (activity and activity.get("due_date")):
            continue
        
        try:
            due_date = datetime.strptime(activity["due_date"], '%Y-%m-%d').date()
            if start_date_filter <= due_date <= end_date_filter:
                filtered_activities.append(activity)
        except (ValueError, TypeError):
            continue # Skip if date is malformed

    # Process the filtered activities into the response model
    response_items = []
    for activity in filtered_activities:
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