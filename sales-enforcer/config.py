# sales-enforcer/config.py

"""
Central configuration for the Sales Scorecard.
-- Updated on 2025-08-25 to use Pipedrive's native rotting feature --
"""

# Official Stage IDs and Order from Pipedrive
STAGES = {
    99: {"name": "Nurture Zone", "order": 1, "points": 0},
    90: {"name": "1. Lead Intake", "order": 2, "points": 10},
    91: {"name": "2. Qualification Completed", "order": 3, "points": 20},
    92: {"name": "3. Pre–Design Intake BAMFAM", "order": 4, "points": 30},
    93: {"name": "4. Design Intake Completed", "order": 5, "points": 40},
    94: {"name": "5. Proposal Presentation / Buying Zone", "order": 6, "points": 50},
    95: {"name": "6. Close (Card / BAMFAM)", "order": 7, "points": 100},
}

# Define compliance rules per stage transition.
COMPLIANCE_RULES = {
    91: [
        {"field": "custom_field_api_key_for_q1", "type": "not_empty", "message": "Qualification Question 1 is missing."},
        {"field": "custom_field_api_key_for_q2", "type": "not_empty", "message": "Qualification Question 2 is missing."},
    ],
    92: [
        {"field": "custom_field_api_key_for_budget", "type": "not_empty", "message": "Budget must be logged."},
        {"field": "custom_field_api_key_for_decision_maker", "type": "not_empty", "message": "Decision Maker must be logged."},
        {"field": "custom_field_api_key_for_urgency", "type": "not_empty", "message": "Urgency must be logged."},
    ],
}

POINT_CONFIG = {
    "weekly_minimum": 100,
    "bonus_lead_intake_same_day": 5,
    "bonus_won_fast_days": 14,
    "bonus_won_fast_points": 50,
}

# Stage order number from which a rotted deal can be revived.
REVIVAL_MINIMUM_STAGE_ORDER = 5 # Corresponds to "4. Design Intake Completed"