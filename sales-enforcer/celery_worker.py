# sales-enforcer/celery_worker.py
import os
import re
from datetime import datetime
from celery import Celery
from dotenv import load_dotenv
from database import SessionLocal
from models import DealStageEvent, PointsLedger, PointEventType
import config
import pipedrive_client
import n8n_client

load_dotenv()

# --- HELPER FUNCTION TO PARSE AZURE REDIS URL ---
def parse_azure_redis_url(azure_url: str) -> str:
    """Converts a complex Azure Redis connection string to a standard Celery broker URL."""
    if not azure_url or not azure_url.startswith('redis-'):
        return azure_url

    try:
        host, params = azure_url.split(',', 1)
        password_match = re.search(r'password=([^,]+)', params)
        password = password_match.group(1) if password_match else ''
        # --- THIS IS THE FIX ---
        # Append the required ssl_cert_reqs parameter for Celery's result backend.
        return f"rediss://:{password}@{host}?ssl_cert_reqs=CERT_NONE"
    except (ValueError, AttributeError):
        print("Warning: Could not parse Azure Redis URL, falling back to the original value.")
        return azure_url

# --- CELERY APP INITIALIZATION ---
raw_redis_url = os.getenv("REDIS_URL")
parsed_redis_url = parse_azure_redis_url(raw_redis_url)

celery_app = Celery("tasks", broker=parsed_redis_url, backend=parsed_redis_url)


# --- ENHANCED HELPER FUNCTIONS ---
def check_compliance(stage_id: int, deal_data: dict) -> (bool, list):
    """Checks complex compliance rules (AND/OR, equals, not_empty)."""
    stage_rules = config.COMPLIANCE_RULES.get(stage_id)
    if not stage_rules:
        return True, []

    condition = stage_rules["condition"]
    rules = stage_rules["rules"]
    failed_messages = []
    passed_rules = 0

    for rule in rules:
        field_key = rule["field"]
        rule_type = rule["type"]
        field_value = deal_data.get(field_key)
        rule_passed = False

        if rule_type == "not_empty" and field_value:
            rule_passed = True
        elif rule_type == "equals" and field_value == rule["value"]:
            rule_passed = True
        
        if rule_passed:
            passed_rules += 1
        else:
            failed_messages.append(rule["message"])

    if condition == "AND" and passed_rules == len(rules):
        return True, []
    if condition == "OR" and passed_rules > 0:
        return True, []

    return False, failed_messages

def apply_bonuses(db_session, deal_data: dict, previous_data: dict):
    """Checks for and applies all relevant bonuses."""
    deal_id, user_id = deal_data["id"], deal_data["user_id"]
    
    if previous_data.get("stage_id") == 90:
        add_date = deal_data.get("add_time", "").split(" ")[0]
        update_date = deal_data.get("update_time", "").split(" ")[0]
        if add_date == update_date:
            points = config.POINT_CONFIG["bonus_lead_intake_same_day"]
            db_session.add(PointsLedger(deal_id=deal_id, user_id=user_id, event_type=PointEventType.BONUS_LEAD_INTAKE_SAME_DAY, points=points, notes="Bonus: Lead Intake same day."))

    if deal_data.get("status") == 'won' and not previous_data.get("status") == 'won':
        add_time = datetime.fromisoformat(deal_data["add_time"])
        won_time = datetime.fromisoformat(deal_data["won_time"])
        days_to_win = (won_time - add_time).days
        if days_to_win <= config.POINT_CONFIG["bonus_won_fast_days"]:
            points = config.POINT_CONFIG["bonus_won_fast_points"]
            db_session.add(PointsLedger(deal_id=deal_id, user_id=user_id, event_type=PointEventType.BONUS_WON_FAST, points=points, notes=f"Bonus: Deal won in {days_to_win} days."))
        
        db_session.add(PointsLedger(deal_id=deal_id, user_id=user_id, event_type=PointEventType.STAGE_ADVANCE, points=config.POINT_CONFIG["won_deal_points"], notes="Deal WON"))
        
        user_data = pipedrive_client.get_user(user_id)
        n8n_client.trigger_won_deal_alert(deal_data, user_data)

# --- MAIN WEBHOOK PROCESSOR ---
@celery_app.task
def process_pipedrive_event(payload: dict):
    if not payload.get("current") or payload.get("event") != "updated.deal":
        return {"status": "Not a deal update event, skipping."}

    current_data = payload["current"]
    previous_data = payload.get("previous", {})
    deal_id, user_id = current_data["id"], current_data["user_id"]
    
    db = SessionLocal()
    try:
        contract_signed = current_data.get(config.AUTOMATION_FIELDS["contract_signed"]) == "Yes"
        payment_taken = current_data.get(config.AUTOMATION_FIELDS["payment_taken"]) == "Yes"
        loss_reason_filled = current_data.get(config.AUTOMATION_FIELDS["loss_reason"])

        if current_data["status"] == "open":
            if contract_signed and payment_taken:
                pipedrive_client.update_deal(deal_id, {"status": "won"})
                return {"status": "Deal automatically moved to WON."}
            if loss_reason_filled:
                pipedrive_client.update_deal(deal_id, {"status": "lost"})
                return {"status": "Deal automatically moved to LOST."}

        if current_data.get("status") != previous_data.get("status"):
            apply_bonuses(db, current_data, previous_data)
            db.commit()

        current_stage_id = current_data["stage_id"]
        previous_stage_id = previous_data.get("stage_id")
        if current_stage_id == previous_stage_id: return {"status": "No stage change."}

        current_stage = config.STAGES.get(current_stage_id)
        previous_stage = config.STAGES.get(previous_stage_id, {"order": 0})
        if not current_stage: return f"Unknown stage_id: {current_stage_id}"
            
        if current_stage["order"] > previous_stage["order"] + 1:
            pipedrive_client.add_note(deal_id, "<b>Compliance Error:</b> Stage was skipped. Deal moved back.")
            pipedrive_client.update_deal(deal_id, {"stage_id": previous_stage_id})
            return {"status": "Stage skip detected."}

        is_compliant, messages = check_compliance(current_stage_id, current_data)
        if not is_compliant:
            full_message = "<b>Compliance Error:</b> Deal moved back. Please complete:<br>- " + "<br>- ".join(messages)
            pipedrive_client.add_note(deal_id, full_message)
            pipedrive_client.add_task(deal_id, user_id, "Fix compliance issues to advance deal")
            pipedrive_client.update_deal(deal_id, {"stage_id": previous_stage_id})
            return {"status": "Not compliant."}

        if not db.query(DealStageEvent).filter_by(deal_id=deal_id, stage_id=current_stage_id).first():
            db.add(DealStageEvent(deal_id=deal_id, stage_id=current_stage_id))
            points_to_add = current_stage.get("points", 0)
            db.add(PointsLedger(deal_id=deal_id, user_id=user_id, event_type=PointEventType.STAGE_ADVANCE, points=points_to_add, notes=f"Advanced to stage: {current_stage['name']}"))
            apply_bonuses(db, current_data, previous_data)
            db.commit()
            return {"status": f"Processed stage progression to {current_stage['name']}."}
        else:
            return {"status": "Event already processed."}
    except Exception as e:
        db.rollback()
        print(f"An error occurred in process_pipedrive_event for deal {deal_id}: {e}")
        return {"status": "Error during processing."}
    finally:
        db.close()

# Keep the apply_rotting_penalties task as it was, it does not need changes.
@celery_app.task
def apply_rotting_penalties():
    pass
