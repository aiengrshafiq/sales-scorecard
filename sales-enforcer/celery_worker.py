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
    stage_rules = config.COMPLIANCE_RULES.get(stage_id)
    if not stage_rules: return True, []
    custom_fields = deal_data.get('custom_fields', {})
    
    def evaluate(ruleset):
        condition = ruleset["condition"]
        rules = ruleset["rules"]
        failed_messages = []
        passed_count = 0
        for rule in rules:
            if "condition" in rule: # Handle nested rule
                passed, messages = evaluate(rule)
                if passed: passed_count += 1
                else: failed_messages.extend(messages)
                continue

            field_key, rule_type = rule["field"], rule["type"]
            field_value = custom_fields.get(field_key)
            rule_passed = False
            if rule_type == "not_empty" and field_value: rule_passed = True
            elif rule_type == "equals" and str(field_value) == rule["value"]: rule_passed = True
            if rule_passed: passed_count += 1
            else: failed_messages.append(rule["message"])
        
        if condition == "AND" and passed_count == len(rules): return True, []
        if condition == "OR" and passed_count > 0: return True, []
        return False, failed_messages

    return evaluate(stage_rules)

def apply_bonuses(db_session, deal_data: dict, previous_data: dict, current_stage_id: int):
    deal_id, user_id = deal_data["id"], deal_data["owner_id"]
    custom_fields = deal_data.get('custom_fields', {})
    
    if previous_data.get("stage_id") == 90:
        add_date = deal_data.get("add_time", "").split("T")[0]
        update_date = deal_data.get("update_time", "").split("T")[0]
        if add_date == update_date:
            db_session.add(PointsLedger(deal_id=deal_id, user_id=user_id, event_type=PointEventType.BONUS, points=config.POINT_CONFIG["bonus_lead_intake_same_day"], notes="Bonus: Lead Intake same day."))

    if current_stage_id == 95 and custom_fields.get(config.AUTOMATION_FIELDS["payment_taken"]) == "Yes":
        update_date_str = deal_data.get("update_time", "").split("T")[0]
        # Check if the deal was in the proposal stage (94) just before this update
        if previous_data.get("stage_id") == 94:
             db_session.add(PointsLedger(deal_id=deal_id, user_id=user_id, event_type=PointEventType.BONUS, points=config.POINT_CONFIG["bonus_proposal_payment_same_day"], notes="Bonus: Payment taken on proposal day."))

    if deal_data.get("status") == 'won' and not previous_data.get("status") == 'won':
        add_time = datetime.fromisoformat(deal_data["add_time"].replace('Z', '+00:00'))
        won_time = datetime.fromisoformat(deal_data["won_time"].replace('Z', '+00:00'))
        days_to_win = (won_time - add_time).days
        if days_to_win <= config.POINT_CONFIG["bonus_won_fast_days"]:
            db_session.add(PointsLedger(deal_id=deal_id, user_id=user_id, event_type=PointEventType.BONUS, points=config.POINT_CONFIG["bonus_won_fast_points"], notes=f"Bonus: Deal won in {days_to_win} days."))
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
    current_data = payload.get("data")
    previous_data = payload.get("previous", {})
    meta_data = payload.get("meta", {})

    if not current_data or meta_data.get("action") != "change":
        return {"status": "Payload did not contain 'data' object or action was not 'change'. Skipping."}

    deal_id, user_id = current_data["id"], current_data["owner_id"]
    custom_fields = current_data.get('custom_fields', {})
    
    db = SessionLocal()
    try:
        was_updated = False
        was_rotten = previous_data.get("rotten_time") is not None
        is_not_rotten_now = current_data.get("rotten_time") is None
        if was_rotten and is_not_rotten_now:
            current_stage = config.STAGES.get(current_data["stage_id"])
            if current_stage and current_stage["order"] >= config.REVIVAL_MINIMUM_STAGE_ORDER:
                suspension_entry = db.query(PointsLedger).filter_by(deal_id=deal_id, event_type=PointEventType.DEAL_ROTTED_SUSPENSION).first()
                if suspension_entry:
                    points_to_restore = abs(suspension_entry.points)
                    db.add(PointsLedger(deal_id=deal_id, user_id=user_id, event_type=PointEventType.DEAL_REVIVED, points=points_to_restore, notes="Deal revived by advancing."))
                    was_updated = True

        contract_signed = custom_fields.get(config.AUTOMATION_FIELDS["contract_signed"]) == "Yes"
        payment_taken = custom_fields.get(config.AUTOMATION_FIELDS["payment_taken"]) == "Yes"
        loss_reason_filled = custom_fields.get(config.AUTOMATION_FIELDS["loss_reason"])
        if current_data["status"] == "open":
            if contract_signed and payment_taken:
                pipedrive_client.update_deal(deal_id, {"status": "won"})
                return {"status": "Deal automatically moved to WON."}
            if loss_reason_filled:
                pipedrive_client.update_deal(deal_id, {"status": "lost"})
                return {"status": "Deal automatically moved to LOST."}

        current_stage_id = current_data["stage_id"]
        previous_stage_id = previous_data.get("stage_id")
        
        if current_data.get("status") != previous_data.get("status"):
            apply_bonuses(db, current_data, previous_data, current_stage_id)
            was_updated = True

        if current_stage_id != previous_stage_id:
            current_stage = config.STAGES.get(current_stage_id)
            previous_stage = config.STAGES.get(previous_stage_id, {"order": 0})
            if not current_stage: return f"Unknown stage_id: {current_stage_id}"
            if current_stage["order"] > previous_stage["order"] + 1:
                pipedrive_client.add_note(deal_id, "<b>Compliance Error:</b> Stage was skipped.")
                pipedrive_client.update_deal(deal_id, {"stage_id": previous_stage_id})
                return {"status": "Stage skip detected."}
            is_compliant, messages = check_compliance(current_stage_id, current_data)
            if not is_compliant:
                full_message = "<b>Compliance Error:</b> Please complete:<br>- " + "<br>- ".join(messages)
                pipedrive_client.add_note(deal_id, full_message)
                pipedrive_client.add_task(deal_id, user_id, "Fix compliance issues to advance deal")
                pipedrive_client.update_deal(deal_id, {"stage_id": previous_stage_id})
                return {"status": "Not compliant."}
            if not db.query(DealStageEvent).filter_by(deal_id=deal_id, stage_id=current_stage_id).first():
                db.add(DealStageEvent(deal_id=deal_id, stage_id=current_stage_id))
                points_to_add = current_stage.get("points", 0)
                db.add(PointsLedger(deal_id=deal_id, user_id=user_id, event_type=PointEventType.STAGE_ADVANCE, points=points_to_add, notes=f"Advanced to stage: {current_stage['name']}"))
                apply_bonuses(db, current_data, previous_data, current_stage_id)
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
