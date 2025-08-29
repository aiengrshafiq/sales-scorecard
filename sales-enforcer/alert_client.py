# sales-enforcer/alert_client.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()

ZAPIER_WEBHOOK_URL_DEAL_WON = os.getenv("ZAPIER_WEBHOOK_URL_DEAL_WON")
ZAPIER_WEBHOOK_URL_MILESTONE = os.getenv("ZAPIER_WEBHOOK_URL_MILESTONE")

def trigger_won_deal_alert(deal_data: dict, user_data: dict):
    if not ZAPIER_WEBHOOK_URL_DEAL_WON:
        print("ZAPIER_WEBHOOK_URL_DEAL_WON is not set. Skipping.")
        return

    try:
        payload = {
            "deal_name": deal_data.get("title"),
            "deal_value": deal_data.get("value"),
            "rep_name": user_data.get("name"),
        }
        requests.post(ZAPIER_WEBHOOK_URL_DEAL_WON, json=payload, timeout=5)
        print(f"Successfully triggered Zapier 'Deal WON' alert for deal {deal_data['id']}.")
    except Exception as e:
        print(f"Failed to trigger Zapier webhook: {e}")

def trigger_milestone_alert(user_data: dict, milestone_rank: str):
    if not ZAPIER_WEBHOOK_URL_MILESTONE:
        print("ZAPIER_WEBHOOK_URL_MILESTONE is not set. Skipping.")
        return

    try:
        payload = {
            "rep_name": user_data.get("name"),
            "rank": milestone_rank,
        }
        requests.post(ZAPIER_WEBHOOK_URL_MILESTONE, json=payload, timeout=5)
        print(f"Successfully triggered Zapier 'Milestone' alert for {user_data.get('name')}.")
    except Exception as e:
        print(f"Failed to trigger Zapier milestone webhook: {e}")