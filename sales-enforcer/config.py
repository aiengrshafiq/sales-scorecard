# sales-enforcer/config.py

"""
Central configuration for the Sales Scorecard.
-- Final production rules and dashboard configuration --
"""

# --- Scorecard Points System ---
STAGES = {
    99: {"name": "Nurture Zone", "order": 1, "points": 0},
    90: {"name": "1. Lead Intake", "order": 2, "points": 10},
    91: {"name": "2. Qualification Completed", "order": 3, "points": 20},
    92: {"name": "3. Pre–Design Intake BAMFAM", "order": 4, "points": 30},
    93: {"name": "4. Design Intake Completed", "order": 5, "points": 40},
    94: {"name": "5. Proposal Presentation / Buying Zone", "order": 6, "points": 50},
    95: {"name": "6. Close (Card / BAMFAM)", "order": 7, "points": 100},
}

POINT_CONFIG = {
    "won_deal_points": 200,
    "weekly_minimum": 150,
    "bonus_lead_intake_same_day": 5,
    "bonus_proposal_payment_same_day": 25,
    "bonus_won_fast_days": 14,
    "bonus_won_fast_points": 50,
}

REVIVAL_MINIMUM_STAGE_ORDER = 5

MILESTONES = {
    "Bronze": 1000,
    "Silver": 2500,
    "Gold": 5000,
}

# --- Automation Fields ---
# Storing both the API key and the required ID for "Yes"
AUTOMATION_FIELDS = {
    "contract_signed":  {"key": "0ede563fbd2d22869b5c63a15ac1f1b8e4ddf610", "yes_id": 91},
    "payment_taken":    {"key": "c61044a44d813064e799a96c88cb55bca465d04e", "yes_id": 90},
    "loss_reason":      {"key": "f7767455d77a063bc765e0b323813f513bcca2f9"},
}

# --- Stage Compliance Checkpoints ---
# This section is correct and requires no changes.
COMPLIANCE_RULES = {
    91: { "condition": "AND", "rules": [
        {"field": "a46e8e4a3b0ec6d6dfe820ace2a80721f7078725", "type": "not_empty", "message": "Qualifying Question 1 is missing."},
        {"field": "aceebe87f042b5cdb1915ceeb604277dbd0072b7", "type": "not_empty", "message": "Qualifying Question 2 is missing."}
    ]},
    92: { "condition": "AND", "rules": [
        {"field": "64cd1cfd01c9046629e178cefb5be2b690bea8a3", "type": "equals_id", "value": 88, "message": "Budget must be confirmed as 'Yes'."},
        {"field": "6ee940cb2e7b5d2e1108ab76b2164771f8678558", "type": "equals_id", "value": 76, "message": "Decision-Maker(s) must be identified as 'Yes'."},
        {"field": "307d3de4715ffcdb8e17cc26bea6b19607519b4e", "type": "not_empty", "message": "Deadline / Buying Window date must be set."}
    ]},
    93: { "condition": "AND", "rules": [
        {"field": "1b8f69dbd9fff59ccf06f157f6141923786e84fc", "type": "not_empty", "message": "Proposal Presentation Date must be set."}
    ]},
    94: { "condition": "AND", "rules": [
        {"field": "f7b50a98745a1a2ec32a92d4bcfb89244fc15f4b", "type": "equals_id", "value": 78, "message": "Design Fee must be paid ('Yes')."},
        {"field": "fb900167fac960c2d59c1f524c3a788568bd48c5", "type": "equals_id", "value": 98, "message": "Decision-Makers for proposal must be confirmed ('Yes')."}
    ]},
    95: { "condition": "AND", "rules": [
        {"condition": "OR", "rules": [
            {"field": "c61044a44d813064e799a96c88cb55bca465d04e", "type": "equals_id", "value": 90, "message": "Payment must be taken."},
            {"field": "844ec4a1daff8bcec5600224c6021aff9550c862", "type": "not_empty", "message": "Final Decision Meeting must be booked."}
        ]}
    ]},
}

# --- Dashboard Configuration ---
DASHBOARD_CONFIG = {
    "quarterly_points_target": 20000,
    "field_keys": {
        "design_fee_paid": "f7b50a98745a1a2ec32a92d4bcfb89244fc15f4b",
        "loss_reason": "f7767455d77a063bc765e0b323813f513bcca2f9",
        "proposal_date": "1b8f69dbd9fff59ccf06f157f6141923786e84fc"
    }
}
