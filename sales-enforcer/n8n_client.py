# sales-enforcer/n8n_client.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()

N8N_WEBHOOK_URL_DEAL_WON = os.getenv("N8N_WEBHOOK_URL_DEAL_WON")

def trigger_won_deal_alert(deal_data: dict, user_data: dict):
    if not N8N_WEBHOOK_URL_DEAL_WON:
        print("N8N_WEBHOOK_URL_DEAL_WON is not set. Skipping notification.")
        return

    try:
        payload = {
            "deal_name": deal_data.get("title"),
            "deal_value": deal_data.get("value"),
            "rep_name": user_data.get("name", "Unknown Rep"), # Use the rep's actual name
        }
        requests.post(N8N_WEBHOOK_URL_DEAL_WON, json=payload, timeout=5)
        print(f"Successfully triggered n8n 'Deal WON' alert for deal {deal_data['id']}.")
    except Exception as e:
        print(f"Failed to trigger n8n webhook: {e}")


# Add this to sales-enforcer/n8n_client.py

# Add the new webhook URL variable at the top
N8N_WEBHOOK_URL_MILESTONE = os.getenv("N8N_WEBHOOK_URL_MILESTONE")

# Add the new trigger function
def trigger_milestone_alert(user_data: dict, milestone_rank: str):
    if not N8N_WEBHOOK_URL_MILESTONE:
        print("N8N_WEBHOOK_URL_MILESTONE is not set. Skipping notification.")
        return

    try:
        payload = {
            "rep_name": user_data.get("name", "Unknown Rep"),
            "rank": milestone_rank,
        }
        requests.post(N8N_WEBHOOK_URL_MILESTONE, json=payload, timeout=5)
        print(f"Successfully triggered n8n 'Milestone' alert for {user_data.get('name')}.")
    except Exception as e:
        print(f"Failed to trigger n8n milestone webhook: {e}")