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
# import alert_client # Commented out to prevent errors

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
    This version is robust against different data types from the Pipedrive API.
    """
    stage_rules = config.COMPLIANCE_RULES.get(stage_id)
    if not stage_rules:
        return True, []

    def evaluate(ruleset):
        condition = ruleset["condition"]
        rules = ruleset["rules"]
        failed_messages = []
        passed_count = 0
        
        for rule in rules:
            if "condition" in rule:
                passed, messages = evaluate(rule)
                if passed:
                    passed_count += 1
                else:
                    failed_messages.extend(messages)
                continue

            field_key = rule["field"]
            rule_type = rule["type"]
            field_value = deal_data.get(field_key)
            
            value_to_check = None
            if isinstance(field_value, dict) and 'id' in field_value:
                value_to_check = field_value['id']
            elif field_value is not None:
                value_to_check = field_value

            rule_passed = False
            if rule_type == "not_empty" and value_to_check is not None:
                rule_passed = True
            elif rule_type == "equals_id" and value_to_check is not None:
                if str(value_to_check) == str(rule["value"]):
                    rule_passed = True
            elif rule_type == "equals" and value_to_check is not None:
                 if str(value_to_check) == str(rule["value"]):
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

def apply_status_change_bonuses(db_session, user_id: int, deal_data: dict, previous_data: dict):
    deal_id = deal_data["id"]
    
    if deal_data.get("status") == 'won' and previous_data.get("status") != 'won':
        add_time = datetime.fromisoformat(deal_data["add_time"].replace('Z', '+00:00'))
        won_time = datetime.fromisoformat(deal_data["won_time"].replace('Z', '+00:00'))
        days_to_win = (won_time - add_time).days
        
        if days_to_win <= config.POINT_CONFIG["bonus_won_fast_days"]:
            db_session.add(PointsLedger(deal_id=deal_id, user_id=user_id, event_type=PointEventType.BONUS, points=config.POINT_CONFIG["bonus_won_fast_points"], notes=f"Bonus: Deal won in {days_to_win} days."))
        
        db_session.add(PointsLedger(deal_id=deal_id, user_id=user_id, event_type=PointEventType.STAGE_ADVANCE, points=config.POINT_CONFIG["won_deal_points"], notes="Deal WON"))
        
def check_and_trigger_milestones(db_session, user_id: int):
    total_score = db_session.query(func.sum(PointsLedger.points)).filter(PointsLedger.user_id == user_id).scalar() or 0
    achieved_milestones = db_session.query(UserMilestone.milestone_rank).filter(UserMilestone.user_id == user_id).all()
    achieved_ranks = [m[0] for m in achieved_milestones]
    for rank, points_required in reversed(list(config.MILESTONES.items())):
        if total_score >= points_required and rank not in achieved_ranks:
            db_session.add(UserMilestone(user_id=user_id, milestone_rank=rank))
            break

@celery_app.task
def process_pipedrive_event(payload: dict):
    print(f"Received payload: {payload}")
    current_data = payload.get("data")
    previous_data = payload.get("previous", {})
    
    if not current_data:
        return {"status": "Payload did not contain 'data' object. Skipping."}

    # --- CRITICAL FIX: Get ID and User ID reliably from the initial payload ---
    deal_id = current_data.get("id")
    user_id = current_data.get("owner_id")
    
    if not deal_id or not user_id:
        return {"status": "Deal ID or Owner ID missing from webhook payload. Skipping."}
    
    db = SessionLocal()
    try:
        was_updated = False
        full_deal_data = pipedrive_client.get_deal(deal_id)
        if not full_deal_data:
            return {"status": f"Could not fetch full details for deal {deal_id}."}

        # Handle status change events
        if current_data.get("status") != previous_data.get("status"):
            apply_status_change_bonuses(db, user_id, full_deal_data, previous_data)
            was_updated = True

        # Handle stage change events
        current_stage_id = current_data.get("stage_id")
        previous_stage_id = previous_data.get("stage_id")
        if current_stage_id is not None and current_stage_id != previous_stage_id:
            current_stage = config.STAGES.get(current_stage_id)
            previous_stage = config.STAGES.get(previous_stage_id, {"order": 0})

            if not current_stage: return f"Unknown stage_id: {current_stage_id}"
            
            if current_stage["order"] > previous_stage["order"]:
                is_compliant, messages = check_compliance(current_stage_id, full_deal_data)
                if not is_compliant:
                    full_message = "<b>Compliance Error:</b> Deal moved back. Please complete required fields for this stage:<br>- " + "<br>- ".join(messages)
                    pipedrive_client.add_note(deal_id, full_message)
                    pipedrive_client.update_deal(deal_id, {"stage_id": previous_stage_id})
                    return {"status": f"Not compliant with stage {current_stage_id}. Deal reverted."}

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
            return {"status": "No changes triggered point updates."}

    except Exception as e:
        db.rollback()
        print(f"FATAL error in process_pipedrive_event for deal {deal_id}: {e}")
        return {"status": "Error during processing."}
    finally:
        db.close()

@celery_app.task
def apply_rotting_penalties():
    print("Running scheduled task: Applying rotting penalties...")
    rotted_deals = pipedrive_client.get_rotted_deals()
    if not rotted_deals:
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
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"An error occurred in apply_rotting_penalties: {e}")
    finally:
        db.close()
    
    return {"status": f"Rotting check complete. Processed {len(rotted_deals)} deals."}

