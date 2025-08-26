# sales-enforcer/pipedrive_client.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN")
BASE_URL = "https://api.pipedrive.com/v1"

def _handle_request_exception(e: requests.exceptions.RequestException, context: str):
    error_message = f"Error during '{context}': {e}"
    if e.response is not None:
        error_message += f" | Status: {e.response.status_code} | Response: {e.response.text}"
    print(error_message)
    raise e

def get_rotted_deals():
    """Fetches all deals currently marked as rotten by Pipedrive."""
    url = f"{BASE_URL}/deals"
    params = {
        "api_token": API_TOKEN,
        "filter_id": 2 # Pipedrive's default filter for "All rotten deals"
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json().get("data", []) or []
    except requests.exceptions.RequestException as e:
        _handle_request_exception(e, "get rotted deals")
        return []

def update_deal(deal_id: int, payload: dict):
    url = f"{BASE_URL}/deals/{deal_id}"
    params = {"api_token": API_TOKEN}
    try:
        response = requests.put(url, params=params, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        _handle_request_exception(e, f"update deal {deal_id}")

def add_note(deal_id: int, content: str):
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
    url = f"{BASE_URL}/activities"
    params = {"api_token": API_TOKEN}
    payload = {"deal_id": deal_id, "user_id": user_id, "subject": subject, "type": "task"}
    try:
        response = requests.post(url, params=params, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        _handle_request_exception(e, f"add task to deal {deal_id}")


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