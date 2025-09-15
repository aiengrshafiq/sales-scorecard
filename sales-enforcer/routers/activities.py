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
    Fetches all open (not done) activities within a given due_date range (inclusive).
    """
    # Use company TZ (assumed Dubai) for date comparisons
    dubai_today = datetime.now(ZoneInfo("Asia/Dubai")).date()

    # Defaults: today .. today+30d
    if start_date is None:
        start_date = dubai_today
    if end_date is None:
        end_date = dubai_today + timedelta(days=30)   # <- fixed the colon

    # v2 fetch + client-side due_date filter
    activities = await pipedrive_client.get_activities_by_due_date_range_async(
        owner_id=user_id,
        start_date=start_date,
        end_date=end_date,
        done=0,
    )

    if not activities:
        return []

    items: List[DueActivityItem] = []
    for a in activities:
        dd_str = a.get("due_date")
        if not dd_str:
            continue
        dd = datetime.strptime(dd_str, "%Y-%m-%d").date()

        items.append(
            DueActivityItem(
                id=a["id"],
                subject=a.get("subject", "No Subject"),
                type=a.get("type", "task"),
                due_date=dd_str,
                # v2 may not include 'owner_name'; fall back gracefully
                owner_name=a.get("owner_name") or a.get("owner_id") and str(a["owner_id"]) or "Unknown",
                deal_id=a.get("deal_id"),
                deal_title=a.get("deal_title", "No Associated Deal"),
                is_overdue=(dd < dubai_today),
            )
        )

    # Sort by due_date ascending (string sort is fine for YYYY-MM-DD)
    return sorted(items, key=lambda x: x.due_date)