# sales-enforcer/celery_worker.py
import os
from datetime import datetime
from celery import Celery
from dotenv import load_dotenv
from database import SessionLocal
from models import DealStageEvent, PointsLedger, PointEventType
import config
import pipedrive_client

import n8n_client

load_dotenv()

celery_app = Celery("tasks", broker=os.getenv("REDIS_URL"), backend=os.getenv("REDIS_URL"))

# --- Helper Functions ---
def check_compliance(stage_id: int, deal_data: dict) -> (bool, list):
    rules = config.COMPLIANCE_RULES.get(stage_id, [])
    if not rules: return True, []
    missing_items = [rule["message"] for rule in rules if not deal_data.get(rule["field"])]
    return not missing_items, missing_items

def apply_bonuses(db_session, deal_data: dict):
    deal_id, user_id = deal_data["id"], deal_data["user_id"]
    if deal_data.get("status") == 'won':
        add_time = datetime.fromisoformat(deal_data["add_time"])
        won_time = datetime.fromisoformat(deal_data["won_time"])
        days_to_win = (won_time - add_time).days
        if days_to_win <= config.POINT_CONFIG["bonus_won_fast_days"]:
            bonus_entry = PointsLedger(deal_id=deal_id, user_id=user_id, event_type=PointEventType.BONUS_WON_FAST, points=config.POINT_CONFIG["bonus_won_fast_points"], notes=f"Bonus: Deal won in {days_to_win} days.")
            db_session.add(bonus_entry)

# --- Main Webhook Processor ---
@celery_app.task
def process_pipedrive_event(payload: dict):
    if not payload.get("current") or payload.get("event") != "updated.deal":
        return {"status": "Not a deal update event, skipping."}

    current_data = payload["current"]
    previous_data = payload.get("previous", {})
    deal_id, user_id = current_data["id"], current_data["user_id"]
    current_stage_id = current_data["stage_id"]
    
    db = SessionLocal()
    try:
        # --- Revival Logic ---
        is_now_rotten = current_data.get("rotten", False)
        was_previously_rotten = previous_data.get("rotten", False)
        current_stage = config.STAGES.get(current_stage_id)

        if was_previously_rotten and not is_now_rotten:
            is_revived = db.query(PointsLedger).filter_by(deal_id=deal_id, event_type=PointEventType.DEAL_REVIVED).first()
            if not is_revived and current_stage and current_stage["order"] >= config.REVIVAL_MINIMUM_STAGE_ORDER:
                original_points = config.STAGES.get(current_data["stage_id"], {}).get("points", 0)
                revival_entry = PointsLedger(deal_id=deal_id, user_id=user_id, event_type=PointEventType.DEAL_REVIVED, points=original_points, notes="Deal revived by advancing.")
                db.add(revival_entry)
                db.commit()
                print(f"Deal {deal_id} has been revived. Restored {original_points} points.")

        # --- Stage Progression & Compliance Logic ---
        previous_stage_id = previous_data.get("stage_id")
        if current_stage_id == previous_stage_id: return {"status": "No stage change."}

        previous_stage = config.STAGES.get(previous_stage_id, {"order": 0})
        if not current_stage: return f"Unknown stage_id: {current_stage_id}"
            
        if current_stage["order"] > previous_stage["order"] + 1:
            pipedrive_client.add_note(deal_id, "<b>Compliance Error:</b> Stage was skipped. Deal moved back.")
            pipedrive_client.update_deal(deal_id, {"stage_id": previous_stage_id})
            return {"status": "Stage skip detected. Pushed back."}

        is_compliant, messages = check_compliance(current_stage_id, current_data)
        if not is_compliant:
            full_message = "<b>Compliance Error:</b> Deal moved back. Please complete:<br>- " + "<br>- ".join(messages)
            pipedrive_client.add_note(deal_id, full_message)
            pipedrive_client.add_task(deal_id, user_id, "Fix compliance issues to advance deal")
            pipedrive_client.update_deal(deal_id, {"stage_id": previous_stage_id})
            return {"status": "Not compliant. Pushed back."}

        if not db.query(DealStageEvent).filter_by(deal_id=deal_id, stage_id=current_stage_id).first():
            db.add(DealStageEvent(deal_id=deal_id, stage_id=current_stage_id))
            points_to_add = current_stage.get("points", 0)
            db.add(PointsLedger(deal_id=deal_id, user_id=user_id, event_type=PointEventType.STAGE_ADVANCE, points=points_to_add, notes=f"Advanced to stage: {current_stage['name']}"))
            apply_bonuses(db, current_data)
            db.commit()
            return {"status": f"Successfully processed stage progression to {current_stage['name']}. Awarded {points_to_add} points."}
        else:
            return {"status": "Event already processed."}
    except Exception as e:
        db.rollback()
        print(f"An error occurred in process_pipedrive_event for deal {deal_id}: {e}")
        return {"status": "Error during processing."}
    finally:
        db.close()

# --- Scheduled Task for Applying Rotting Penalties ---
@celery_app.task
def apply_rotting_penalties():
    """Scheduled task to apply penalties to deals Pipedrive has marked as rotten."""
    print("Running scheduled task: Applying rotting penalties...")
    rotted_deals = pipedrive_client.get_rotted_deals()
    if not rotted_deals:
        return {"status": "No rotted deals found."}

    db = SessionLocal()
    try:
        for deal in rotted_deals:
            deal_id, user_id, stage_id = deal["id"], deal["user_id"], deal["stage_id"]
            is_penalized = db.query(PointsLedger).filter_by(deal_id=deal_id, event_type=PointEventType.DEAL_ROTTED_SUSPENSION).first()
            
            if not is_penalized:
                stage_points = config.STAGES.get(stage_id, {}).get("points", 0)
                if stage_points > 0:
                    penalty = PointsLedger(deal_id=deal_id, user_id=user_id, event_type=PointEventType.DEAL_ROTTED_SUSPENSION, points=-stage_points, notes=f"Deal rotted in stage {config.STAGES.get(stage_id, {}).get('name', 'Unknown')}")
                    db.add(penalty)
                    print(f"Applied penalty of {-stage_points} to rotted deal {deal_id}.")
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"An error occurred in apply_rotting_penalties: {e}")
    finally:
        db.close()
    
    return {"status": f"Rotting check complete. Processed {len(rotted_deals)} deals."}


def apply_bonuses(db_session, deal_data: dict):
    # ... (existing bonus logic)
    if deal_data.get("status") == 'won':
        # ... (fast win bonus logic)

        # NEW: Trigger the n8n celebration alert
        user_data = pipedrive_client.get_user(deal_data["user_id"])
        n8n_client.trigger_won_deal_alert(deal_data, user_data)