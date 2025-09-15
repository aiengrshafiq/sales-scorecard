# sales-enforcer/pipedrive_client.py
import os
import requests
import httpx
from dotenv import load_dotenv
from datetime import date

load_dotenv()

API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN")

# ✅ FIXED: Using correct V1 and V2 base URLs
API_HOST = "https://api.pipedrive.com"
V1_BASE = f"{API_HOST}/v1"
V2_BASE = f"{API_HOST}/api/v2"


# --- Synchronous Functions (Using V1) ---
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

async def get_deals_from_pipeline_async(
    pipeline_id: int,
    user_id: int | None = None,
    status: str = "open"
):
    """
    Async: Fetch all deals from a specific pipeline using the Pipedrive v2 API.
    Uses modern cursor-based pagination and sorts by newest first.
    """
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
    """Async: Fetches activities for a SPECIFIC deal using the correct endpoint."""
    # Correct endpoint: /deals/{id}/activities
    url = f"{V1_BASE}/deals/{deal_id}/activities"
    params = {
        "api_token": API_TOKEN,
        "start": 0,
        "limit": limit,
    }
    if done is not None:
        params["done"] = done

    items = []
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # This endpoint also uses start/limit pagination
            while True:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                body = resp.json()
                data = body.get("data") or []
                items.extend(data)

                # Stop if we've fetched enough according to the limit
                if limit and len(items) >= limit:
                    return items[:limit]

                pagination = body.get("additional_data", {}).get("pagination", {})
                if not pagination or not pagination.get("more_items_in_collection"):
                    break
                
                next_start = pagination.get("next_start")
                if next_start is not None:
                    params["start"] = next_start
                else: # Fallback if next_start isn't provided
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
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json().get("data", [])
            return [user for user in data if user.get("active_flag")] if data else []
    except httpx.RequestError as e:
        return _handle_async_request_exception(e, "get all users")


# ✅ ADD THIS NEW ASYNC FUNCTION AT THE END OF THE FILE

async def get_all_open_activities_async(user_id: int | None = None):
    """
    Async: Fetches all open (not done) activities, with pagination.
    Optionally filters by a specific user.
    """
    url = f"{V1_BASE}/activities"
    params = {
        "api_token": API_TOKEN,
        "done": 0, # 0 = not done
        "limit": 500
    }
    if user_id:
        params["user_id"] = user_id

    all_activities = []
    start = 0

    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            params["start"] = start
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                body = resp.json()
                data = body.get("data") or []
                if not data:
                    break
                
                all_activities.extend(data)
                
                pagination = body.get("additional_data", {}).get("pagination", {})
                if not pagination or not pagination.get("more_items_in_collection"):
                    break
                start += len(data)

            except httpx.RequestError as e:
                _handle_async_request_exception(e, f"get all open activities")
                return []
    return all_activities