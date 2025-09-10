# sales-enforcer/pipedrive_client.py
import os
import requests
import httpx
from dotenv import load_dotenv
from datetime import date

load_dotenv()

API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN")
BASE_URL = "https://api.pipedrive.com/v1"

# --- All synchronous functions are correct and remain unchanged ---
# ... (get_deal, get_user, etc.) ...
def _handle_request_exception(e: requests.exceptions.RequestException, context: str):
    error_message = f"Error during '{context}': {e}";print(error_message);return None
def get_deal(deal_id: int):
    url = f"{BASE_URL}/deals/{deal_id}";params = {"api_token": API_TOKEN};try:response = requests.get(url, params=params);response.raise_for_status();return response.json().get("data", None)
    except requests.exceptions.RequestException as e:return _handle_request_exception(e, f"get deal {deal_id}")
def get_user(user_id: int):
    url = f"{BASE_URL}/users/{user_id}";params = {"api_token": API_TOKEN};try:response = requests.get(url, params=params);response.raise_for_status();return response.json().get("data", {})
    except requests.exceptions.RequestException as e: _handle_request_exception(e, f"get user {user_id}");return {}
def get_deals(params: dict = None):
    if params is None: params = {};url = f"{BASE_URL}/deals";params["api_token"] = API_TOKEN;all_deals = [];start = 0;limit = 500
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
    url = f"{BASE_URL}/deals/{deal_id}";params = {"api_token": API_TOKEN}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client: response = await client.get(url, params=params);response.raise_for_status();return response.json().get("data", None)
    except httpx.RequestError as e: return _handle_async_request_exception(e, f"get deal {deal_id}")

# ✅ FIXED: Re-implementing get_deals_async to be a robust, paginating function.
# This replaces the flawed timeline function.
async def get_deals_async(params: dict = None):
    """Async: Fetches deals from Pipedrive with server-side filters and pagination."""
    if params is None: params = {}
    
    url = f"{BASE_URL}/deals"
    request_params = params.copy()
    request_params["api_token"] = API_TOKEN
    
    all_deals = []
    start = 0
    limit = 500 # Pipedrive's max limit per page

    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            request_params["start"] = start
            request_params["limit"] = limit
            try:
                response = await client.get(url, params=request_params)
                response.raise_for_status()
                data = response.json().get("data", [])
                
                if not data: break
                
                all_deals.extend(data)
                
                pagination = response.json().get("additional_data", {}).get("pagination", {})
                if not pagination or not pagination.get("more_items_in_collection"): break
                
                start += len(data)
            
            except httpx.RequestError as e:
                _handle_async_request_exception(e, f"get deals with params {request_params}")
                return []
    
    return all_deals

async def get_deal_activities_async(deal_id: int):
    url = f"{BASE_URL}/activities";params = {"api_token": API_TOKEN, "deal_id": deal_id, "limit": 10, "done": 1} 
    try:
        async with httpx.AsyncClient(timeout=30.0) as client: response = await client.get(url, params=params);response.raise_for_status();return response.json().get("data", [])
    except httpx.RequestError as e: return _handle_async_request_exception(e, f"get activities for deal {deal_id}")

async def get_all_stages_async():
    url = f"{BASE_URL}/stages";params = {"api_token": API_TOKEN}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client: response = await client.get(url, params=params);response.raise_for_status();return response.json().get("data", [])
    except httpx.RequestError as e: return _handle_async_request_exception(e, "get all stages")

async def get_all_users_async():
    url = f"{BASE_URL}/users";params = {"api_token": API_TOKEN}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params);response.raise_for_status();data = response.json().get("data", [])
            return [user for user in data if user.get("active_flag")] if data else []
    except httpx.RequestError as e: return _handle_async_request_exception(e, "get all users")