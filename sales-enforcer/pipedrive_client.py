import os
import requests
import httpx
from dotenv import load_dotenv
from datetime import date
from typing import Optional, List, Dict
import asyncio

load_dotenv()

API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN")
API_HOST = "https://api.pipedrive.com"
V1_BASE = f"{API_HOST}/v1"
V2_BASE = f"{API_HOST}/api/v2"

# --- Synchronous Functions ---

def _handle_request_exception(e: requests.exceptions.RequestException, context: str):
    error_message = f"Error during '{context}': {e}"
    if e.response is not None:
        error_message += f" | Status: {e.response.status_code} | Response: {e.response.text}"
    print(error_message)
    return None

def get_deal(deal_id: int):
    url = f"{V1_BASE}/deals/{deal_id}"
    params = {"api_token": API_TOKEN}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json().get("data", None)
    except requests.exceptions.RequestException as e:
        return _handle_request_exception(e, f"get deal {deal_id}")

def get_user(user_id: int):
    url = f"{V1_BASE}/users/{user_id}"
    params = {"api_token": API_TOKEN}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json().get("data", {})
    except requests.exceptions.RequestException as e:
        _handle_request_exception(e, f"get user {user_id}")
        return {}

def get_deals(params: dict = None):
    if params is None:
        params = {}
    url = f"{V1_BASE}/deals"
    params["api_token"] = API_TOKEN
    all_deals = []
    start = 0
    limit = 500
    while True:
        params["start"] = start
        params["limit"] = limit
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json().get("data", [])
            if not data:
                break
            all_deals.extend(data)
            pagination = response.json().get("additional_data", {}).get("pagination", {})
            if not pagination or not pagination.get("more_items_in_collection"):
                break
            start += len(data)
        except requests.exceptions.RequestException as e:
            _handle_request_exception(e, f"get deals with params {params}")
            return []
    return all_deals


# --- Asynchronous Functions ---

def _handle_async_request_exception(e: httpx.RequestError, context: str):
    error_message = f"Error during async '{context}': {e}"
    if hasattr(e, 'response') and e.response is not None:
        error_message += f" | Status: {e.response.status_code} | Response: {e.response.text}"
    print(error_message)
    return None

async def get_deal_async(deal_id: int):
    url = f"{V1_BASE}/deals/{deal_id}"
    params = {"api_token": API_TOKEN}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json().get("data", None)
    except httpx.RequestError as e:
        return _handle_async_request_exception(e, f"get deal {deal_id}")

async def get_deals_from_pipeline_async(pipeline_id: int, user_id: int | None = None, status: str = "open"):
    url = f"{V2_BASE}/deals"
    params = {
        "api_token": API_TOKEN,
        "pipeline_id": pipeline_id,
        "status": status,
        "sort_by": "add_time",
        "sort_direction": "desc",
        "limit": 500
    }
    if user_id:
        params["owner_id"] = user_id

    all_deals = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            body = resp.json()
            data = body.get("data", []) or []
            all_deals.extend(data)
            cursor = body.get("additional_data", {}).get("next_cursor")
            if not cursor:
                break
            params["cursor"] = cursor
            params.pop("start", None)
            params.pop("limit", None)
    return all_deals

async def get_deal_activities_async(deal_id: int, limit: int = 10, done: int = 1):
    url = f"{V1_BASE}/deals/{deal_id}/activities"
    params = {"api_token": API_TOKEN, "start": 0, "limit": limit}
    if done is not None:
        params["done"] = done

    items = []
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                body = resp.json()
                data = body.get("data") or []
                items.extend(data)
                if limit and len(items) >= limit:
                    return items[:limit]
                pagination = body.get("additional_data", {}).get("pagination", {})
                if not pagination or not pagination.get("more_items_in_collection"):
                    break
                next_start = pagination.get("next_start")
                if next_start is not None:
                    params["start"] = next_start
                else:
                    break
    except httpx.RequestError as e:
        return _handle_async_request_exception(e, f"get activities for deal {deal_id}")
    return items

async def get_all_stages_async():
    url = f"{V1_BASE}/stages"
    params = {"api_token": API_TOKEN}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json().get("data", [])
    except httpx.RequestError as e:
        return _handle_async_request_exception(e, "get all stages")

async def get_all_users_async():
    url = f"{V1_BASE}/users"
    params = {"api_token": API_TOKEN}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json().get("data", []) or []
        return [u for u in data if u.get("active_flag")]

async def get_activities_by_due_date_range_v2_async(
    owner_id: Optional[int],
    start_date: date,
    end_date: date,
    done: bool = False
) -> List[Dict]:
    url = f"{V2_BASE}/activities"
    params = {
        "api_token": API_TOKEN,
        "sort_by": "due_date",
        "sort_direction": "asc",
        "limit": 500,
        "done": done,
    }
    if owner_id:
        params["owner_id"] = owner_id

    results: List[Dict] = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        cursor = None
        while True:
            if cursor:
                params["cursor"] = cursor
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            body = resp.json() or {}
            data = body.get("data") or []

            for a in data:
                dd = a.get("due_date")
                if not dd:
                    continue
                d = date.fromisoformat(dd)
                
                if d > end_date:
                    # Sort is ascending, so we can stop fetching pages
                    return results
                
                if start_date <= d <= end_date:
                    results.append(a)

            cursor = (body.get("additional_data") or {}).get("next_cursor")
            if not cursor:
                break
    return results

async def get_due_activities_all_salespersons_async(
    start_date: date,
    end_date: date,
    done: bool = False
) -> List[Dict]:
    users = await get_all_users_async()
    
    async def fetch_for_user(user):
        uid = user.get("id")
        if not uid: return []
        items = await get_activities_by_due_date_range_v2_async(
            owner_id=uid, start_date=start_date, end_date=end_date, done=done,
        )
        owner_name = user.get("name") or str(uid)
        for it in items:
            it.setdefault("owner_name", owner_name)
        return items

    results = await asyncio.gather(*(fetch_for_user(u) for u in users))
    all_items: List[Dict] = []
    for user_items in results:
        all_items.extend(user_items)
        
    return all_items