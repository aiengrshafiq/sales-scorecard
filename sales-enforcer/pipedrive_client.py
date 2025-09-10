# sales-enforcer/pipedrive_client.py
import os
import requests
import httpx
from dotenv import load_dotenv
from datetime import date

load_dotenv()

API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN")

# ✅ FIXED: Using correct V1 and V2 base URLs
API_HOST = "https://pipedrive.com" # Using the base host
V1_BASE = f"{API_HOST}/v1"
V2_BASE = f"{API_HOST}/api/v2"


# --- Synchronous Functions (Using V1) ---
def _handle_request_exception(e: requests.exceptions.RequestException, context: str):
    error_message = f"Error during '{context}': {e}";print(error_message);return None
def get_deal(deal_id: int):
    url = f"{V1_BASE}/deals/{deal_id}";params = {"api_token": API_TOKEN};try:response = requests.get(url, params=params);response.raise_for_status();return response.json().get("data", None)
    except requests.exceptions.RequestException as e:return _handle_request_exception(e, f"get deal {deal_id}")
def get_user(user_id: int):
    url = f"{V1_BASE}/users/{user_id}";params = {"api_token": API_TOKEN};try:response = requests.get(url, params=params);response.raise_for_status();return response.json().get("data", {})
    except requests.exceptions.RequestException as e: _handle_request_exception(e, f"get user {user_id}");return {}
def get_deals(params: dict = None):
    if params is None: params = {};url = f"{V1_BASE}/deals";params["api_token"] = API_TOKEN;all_deals = [];start = 0;limit = 500
    while True:
        params["start"] = start;params["limit"] = limit
        try:
            response = requests.get(url, params=params);response.raise_for_status();data = response.json().get("data", [])
            if not data: break
            all_deals.extend(data)
            pagination = response.json().get("additional_data", {}).get("pagination", {})
            if not pagination or not pagination.get("more_items_in_collection"): break
            start += len(data)
        except requests.exceptions.RequestException as e: _handle_request_exception(e, f"get deals with params {params}");return []
    return all_deals


# --- Asynchronous Functions ---
def _handle_async_request_exception(e: httpx.RequestError, context: str):
    error_message = f"Error during async '{context}': {e}";print(error_message);return None

async def get_deal_async(deal_id: int):
    url = f"{V1_BASE}/deals/{deal_id}";params = {"api_token": API_TOKEN}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client: response = await client.get(url, params=params);response.raise_for_status();return response.json().get("data", None)
    except httpx.RequestError as e: return _handle_async_request_exception(e, f"get deal {deal_id}")

# ✅ FIXED: This is the correct v2 function that replaces the old, buggy v1 attempts.
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
        # Note: v2 API uses 'owner_id' for the user filter
        params["owner_id"] = user_id

    all_deals = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            body = resp.json()
            data = body.get("data", []) or []
            all_deals.extend(data)

            # v2 uses cursor-based pagination, which is more reliable
            cursor = body.get("additional_data", {}).get("next_cursor")
            if not cursor:
                break
            params["cursor"] = cursor
            # Remove start/limit as they are not used with cursors
            params.pop("start", None)
            params.pop("limit", None)
            
    return all_deals


async def get_deal_activities_async(deal_id: int):
    url = f"{V1_BASE}/activities";params = {"api_token": API_TOKEN, "deal_id": deal_id, "limit": 10, "done": 1} 
    try:
        async with httpx.AsyncClient(timeout=30.0) as client: response = await client.get(url, params=params);response.raise_for_status();return response.json().get("data", [])
    except httpx.RequestError as e: return _handle_async_request_exception(e, f"get activities for deal {deal_id}")

async def get_all_stages_async():
    url = f"{V1_BASE}/stages";params = {"api_token": API_TOKEN}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client: response = await client.get(url, params=params);response.raise_for_status();return response.json().get("data", [])
    except httpx.RequestError as e: return _handle_async_request_exception(e, "get all stages")

async def get_all_users_async():
    url = f"{V1_BASE}/users";params = {"api_token": API_TOKEN}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params);response.raise_for_status();data = response.json().get("data", [])
            return [user for user in data if user.get("active_flag")] if data else []
    except httpx.RequestError as e: return _handle_async_request_exception(e, "get all users")