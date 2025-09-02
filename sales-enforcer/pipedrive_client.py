# sales-enforcer/pipedrive_client.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN")
BASE_URL = "https://api.pipedrive.com/v1"

def _handle_request_exception(e: requests.exceptions.RequestException, context: str):
    """A helper to print detailed error messages."""
    error_message = f"Error during '{context}': {e}"
    if e.response is not None:
        error_message += f" | Status: {e.response.status_code} | Response: {e.response.text}"
    print(error_message)
    return None

def get_deal(deal_id: int):
    """Gets a single deal's full details from Pipedrive."""
    url = f"{BASE_URL}/deals/{deal_id}"
    params = {"api_token": API_TOKEN}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json().get("data", {})
    except requests.exceptions.RequestException as e:
        _handle_request_exception(e, f"get deal {deal_id}")
        return {}

def get_user(user_id: int):
    """Gets user details from Pipedrive."""
    url = f"{BASE_URL}/users/{user_id}"
    params = {"api_token": API_TOKEN}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json().get("data", {})
    except requests.exceptions.RequestException as e:
        _handle_request_exception(e, f"get user {user_id}")
        return {}

def get_deals(params: dict = None):
    """
    Fetches deals from Pipedrive with optional filters and handles pagination.
    """
    if params is None:
        params = {}
    
    url = f"{BASE_URL}/deals"
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

def get_rotted_deals():
    """Fetches all deals currently marked as rotten."""
    return get_deals({"filter_id": 2})

def update_deal(deal_id: int, payload: dict):
    """Updates a deal in Pipedrive."""
    url = f"{BASE_URL}/deals/{deal_id}"
    params = {"api_token": API_TOKEN}
    try:
        response = requests.put(url, params=params, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        _handle_request_exception(e, f"update deal {deal_id}")

def add_note(deal_id: int, content: str):
    """Adds a note to a deal."""
    url = f"{BASE_URL}/notes"
    params = {"api_token": API_TOKEN}
    payload = {"deal_id": deal_id, "content": content}
    try:
        response = requests.post(url, params=params, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        _handle_request_exception(e, f"add note to deal {deal_id}")

def add_task(deal_id: int, user_id: int, subject: str):
    """Adds a task (activity) to a deal."""
    url = f"{BASE_URL}/activities"
    params = {"api_token": API_TOKEN}
    payload = {"deal_id": deal_id, "user_id": user_id, "subject": subject, "type": "task"}
    try:
        response = requests.post(url, params=params, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        _handle_request_exception(e, f"add task to deal {deal_id}")
