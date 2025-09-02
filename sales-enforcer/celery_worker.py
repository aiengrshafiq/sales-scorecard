# sales-enforcer/celery_worker.py
import os
import re
from datetime import datetime
from celery import Celery
from dotenv import load_dotenv
from sqlalchemy import func
from database import SessionLocal
from models import DealStageEvent, PointsLedger, PointEventType, UserMilestone
import config
import pipedrive_client
import alert_client

load_dotenv()

def parse_azure_redis_url(azure_url: str) -> str:
    if not azure_url or not azure_url.startswith('redis-'): return azure_url
    try:
        host, params = azure_url.split(',', 1)
        password_match = re.search(r'password=([^,]+)', params)
        password = password_match.group(1) if password_match else ''
        return f"rediss://:{password}@{host}?ssl_cert_reqs=CERT_NONE"
    except (ValueError, AttributeError):
        print("Warning: Could not parse Azure Redis URL, falling back to original value.")
        return azure_url

raw_redis_url = os.getenv("REDIS_URL")
parsed_redis_url = parse_azure_redis_url(raw_redis_url)
celery_app = Celery("tasks", broker=parsed_redis_url, backend=parsed_redis_url)

def check_compliance(stage_id: int, deal_data: dict) -> (bool, list):
    """
    Evaluates if a deal meets the compliance rules for a given stage.
    """
    stage_rules = config.COMPLIANCE_RULES.get(stage_id)
    if not stage_rules:
        return True, []

    # Pipedrive API v1 sends custom field values directly in the deal object,
    # not in a nested 'custom_fields' object. We'll check the root of the deal data.
    
    def evaluate(ruleset):
        condition = ruleset["condition"]
        rules = ruleset["rules"]
        failed_messages = []
        passed_count = 0
        
        for rule in rules:
            # Handle nested conditions (like OR within an AND)
            if "condition" in rule:
                passed, messages = evaluate(rule)
                if passed:
                    passed_count += 1
                else:
                    failed_messages.extend(messages)
                continue

            field_key = rule["field"]
            rule_type = rule["type"]
            # Get the value from the main deal data dictionary
            field_value = deal_data.get(field_key)
            
            rule_passed = False
            if rule_type == "not_empty" and field_value:
                rule_passed = True
            # --- THIS IS THE NEW LINE TO FIX THE ISSUE ---
            elif rule_type == "equals_id" and field_value is not None and int(field_value) == rule["value"]:
                rule_passed = True
            elif rule_type == "equals" and str(field_value) == str(rule["value"]):
                rule_passed = True

            if rule_passed:
                passed_count += 1
            else:
                failed_messages.append(rule["message"])
        
        if condition == "AND" and passed_count == len(rules):
            return True, []
        if condition == "OR" and passed_count > 0:
            return True, []
            
        return False, failed_messages

    return evaluate(stage_rules)

def apply_bonuses(db_session, deal_data: dict, previous_data: dict):
    deal_id, user_id = deal_data["id"], deal_data["user_id"]
    
    # Bonus for same-day lead intake
    if previous_data.get("stage_id") == 90:
        add_date = deal_data.get("add_time", "").split("T")[0]
        update_date = deal_data.get("update_time", "").split("T")[0]
        if add_date == update_date:
            db_session.add(PointsLedger(deal_id=deal_id, user_id=user_id, event_type=PointEventType.BONUS, points=config.POINT_CONFIG["bonus_lead_intake_same_day"], notes="Bonus: Lead Intake same day."))

    # Bonus for winning a deal quickly
    if deal_data.get("status") == 'won' and previous_data.get("status") != 'won':
        add_time = datetime.fromisoformat(deal_data["add_time"].replace('Z', '+00:00'))
        won_time = datetime.fromisoformat(deal_data["won_time"].replace('Z', '+00:00'))
        days_to_win = (won_time - add_time).days
        if days_to_win <= config.POINT_CONFIG["bonus_won_fast_days"]:
            db_session.add(PointsLedger(deal_id=deal_id, user_id=user_id, event_type=PointEventType.BONUS, points=config.POINT_CONFIG["bonus_won_fast_points"], notes=f"Bonus: Deal won in {days_to_win} days."))
        
        # Award points for winning the deal itself
        db_session.add(PointsLedger(deal_id=deal_id, user_id=user_id, event_type=PointEventType.STAGE_ADVANCE, points=config.POINT_CONFIG["won_deal_points"], notes="Deal WON"))
        user_data = pipedrive_client.get_user(user_id)
        alert_client.trigger_won_deal_alert(deal_data, user_data)

def check_and_trigger_milestones(db_session, user_id: int):
    total_score = db_session.query(func.sum(PointsLedger.points)).filter(PointsLedger.user_id == user_id).scalar() or 0
    achieved_milestones = db_session.query(UserMilestone.milestone_rank).filter(UserMilestone.user_id == user_id).all()
    achieved_ranks = [m[0] for m in achieved_milestones]
    for rank, points_required in reversed(list(config.MILESTONES.items())):
        if total_score >= points_required and rank not in achieved_ranks:
            db_session.add(UserMilestone(user_id=user_id, milestone_rank=rank))
            user_data = pipedrive_client.get_user(user_id)
            alert_client.trigger_milestone_alert(user_data, rank)
            break

@celery_app.task
def process_pipedrive_event(payload: dict):
    print(f"Received payload: {payload}")
    # CRITICAL FIX: Use 'current' for v2 webhooks, not 'data'
    current_data = payload.get("current")
    previous_data = payload.get("previous", {})
    
    if not current_data:
        return {"status": "Payload did not contain 'current' data object. Skipping."}

    deal_id, user_id = current_data["id"], current_data["user_id"]
    
    db = SessionLocal()
    try:
        was_updated = False
        full_deal_data = pipedrive_client.get_deal(deal_id)
        if not full_deal_data:
            return {"status": f"Could not fetch full details for deal {deal_id}."}

        # --- Automatic Status Change Logic ---
        contract_field = config.AUTOMATION_FIELDS["contract_signed"]
        payment_field = config.AUTOMATION_FIELDS["payment_taken"]
        loss_reason_field = config.AUTOMATION_FIELDS["loss_reason"]

        contract_signed = str(full_deal_data.get(contract_field["key"])) == str(contract_field["yes_id"])
        payment_taken = str(full_deal_data.get(payment_field["key"])) == str(payment_field["yes_id"])
        loss_reason_filled = full_deal_data.get(loss_reason_field["key"])

        if full_deal_data["status"] == "open":
            if contract_signed and payment_taken:
                pipedrive_client.update_deal(deal_id, {"status": "won"})
                return {"status": "Deal automatically moved to WON."}
            if loss_reason_filled:
                pipedrive_client.update_deal(deal_id, {"status": "lost"})
                return {"status": "Deal automatically moved to LOST."}

        # --- Status Change Event (e.g., manually moved to Won/Lost) ---
        if current_data.get("status") != previous_data.get("status"):
            apply_bonuses(db, full_deal_data, previous_data)
            was_updated = True

        # --- Stage Change Event ---
        current_stage_id = current_data["stage_id"]
        previous_stage_id = previous_data.get("stage_id")
        if current_stage_id != previous_stage_id:
            current_stage = config.STAGES.get(current_stage_id)
            previous_stage = config.STAGES.get(previous_stage_id, {"order": 0})

            if not current_stage: return f"Unknown stage_id: {current_stage_id}"
            
            # Stage Skip Check
            if current_stage["order"] > previous_stage["order"] + 1:
                pipedrive_client.add_note(deal_id, "<b>Compliance Error:</b> Stage was skipped. Deal moved back.")
                pipedrive_client.update_deal(deal_id, {"stage_id": previous_stage_id})
                return {"status": "Stage skip detected."}

            # Compliance Check
            is_compliant, messages = check_compliance(previous_stage_id, full_deal_data)
            if not is_compliant:
                full_message = "<b>Compliance Error:</b> Please complete requirements for the previous stage before advancing:<br>- " + "<br>- ".join(messages)
                pipedrive_client.add_note(deal_id, full_message)
                pipedrive_client.update_deal(deal_id, {"stage_id": previous_stage_id})
                return {"status": "Not compliant with previous stage."}

            # Award points for the new stage if it's the first time
            if not db.query(DealStageEvent).filter_by(deal_id=deal_id, stage_id=current_stage_id).first():
                db.add(DealStageEvent(deal_id=deal_id, stage_id=current_stage_id))
                points_to_add = current_stage.get("points", 0)
                if points_to_add > 0:
                  db.add(PointsLedger(deal_id=deal_id, user_id=user_id, event_type=PointEventType.STAGE_ADVANCE, points=points_to_add, notes=f"Advanced to stage: {current_stage['name']}"))
                  was_updated = True

        if was_updated:
            db.commit()
            check_and_trigger_milestones(db, user_id)
            return {"status": "Processed successfully with point updates."}
        else:
            return {"status": "No point updates to process."}

    except Exception as e:
        db.rollback()
        print(f"An error occurred in process_pipedrive_event for deal {deal_id}: {e}")
        return {"status": "Error during processing."}
    finally:
        db.close()

@celery_app.task
def apply_rotting_penalties():
    print("Running scheduled task: Applying rotting penalties...")
    rotted_deals = pipedrive_client.get_rotted_deals()
    if not rotted_deals:
        print("No rotted deals found.")
        return {"status": "No rotted deals found."}

    db = SessionLocal()
    try:
        for deal in rotted_deals:
            deal_id, user_id, stage_id = deal["id"], deal["owner_id"], deal["stage_id"]
            is_penalized = db.query(PointsLedger).filter_by(deal_id=deal_id, event_type=PointEventType.DEAL_ROTTED_SUSPENSION).first()
            if not is_penalized:
                stage_points = config.STAGES.get(stage_id, {}).get("points", 0)
                if stage_points > 0:
                    penalty = PointsLedger(deal_id=deal_id, user_id=user_id, event_type=PointEventType.DEAL_ROTTED_SUSPENSION, points=-stage_points, notes=f"Deal rotted in stage '{config.STAGES.get(stage_id, {}).get('name', 'Unknown')}'")
                    db.add(penalty)
                    print(f"Applied penalty of {-stage_points} to rotted deal {deal_id}.")
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"An error occurred in apply_rotting_penalties: {e}")
    finally:
        db.close()
    
    return {"status": f"Rotting check complete. Processed {len(rotted_deals)} deals."}
