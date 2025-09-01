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
    raise e

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

def get_rotted_deals():
    """Fetches all deals currently marked as rotten by Pipedrive."""
    url = f"{BASE_URL}/deals"
    # Pipedrive's API uses a filter for rotten deals. The filter_id for "All rotten deals" is '2'.
    params = {
        "api_token": API_TOKEN,
        "filter_id": 2
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        # The actual deal objects are in the 'data' key of the response
        return response.json().get("data", []) or []
    except requests.exceptions.RequestException as e:
        _handle_request_exception(e, "get rotted deals")
        return []

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
