# sales-enforcer/config.py

"""
Central configuration for the Sales Scorecard.
-- Final production rules based on CEO feedback (2025-08-26) --
"""

# --- Scorecard Points System ---
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

# Bonus points configuration
POINT_CONFIG = {
    "won_deal_points": 200,
    "weekly_minimum": 150,
    "bonus_lead_intake_same_day": 5,
    "bonus_proposal_payment_same_day": 25,
    "bonus_won_fast_days": 14,
    "bonus_won_fast_points": 50,
}

# Stage order number from which a rotted deal can be revived.
REVIVAL_MINIMUM_STAGE_ORDER = 5 # "4. Design Intake Completed"

# --- Stage Compliance Checkpoints ---
# You MUST replace these placeholder keys with your actual Pipedrive API keys.
# To find a field's API key, go to Settings > Data fields, and click on the "..." for a field.
COMPLIANCE_RULES = {
    # Target Stage ID: { rules }
    91: { # Rules for entering '2. Qualification Completed'
        "condition": "AND",
        "rules": [
            {"field": "a46e8e4a3b0ec6d6dfe820ace2a80721f7078725", "type": "not_empty", "message": "Qualifying Question 1 is missing."},
            {"field": "aceebe87f042b5cdb1915ceeb604277dbd0072b7", "type": "not_empty", "message": "Qualifying Question 2 is missing."},
        ]
    },
    92: { # Rules for entering '3. Pre–Design Intake BAMFAM'
        "condition": "AND",
        "rules": [
            {"field": "64cd1cfd01c9046629e178cefb5be2b690bea8a3", "type": "equals", "value": "Yes", "message": "Budget must be confirmed as 'Yes'."},
            {"field": "6ee940cb2e7b5d2e1108ab76b2164771f8678558", "type": "equals", "value": "Yes", "message": "Decision-Maker(s) must be identified as 'Yes'."},
            {"field": "307d3de4715ffcdb8e17cc26bea6b19607519b4e", "type": "not_empty", "message": "Deadline / Buying Window date must be set."},
        ]
    },
    93: { # Rules for entering '4. Design Intake Completed'
        "condition": "AND",
        "rules": [
            {"field": "1b8f69dbd9fff59ccf06f157f6141923786e84fc", "type": "not_empty", "message": "Proposal Presentation Date must be set."},
        ]
    },
    94: { # Rules for entering '5. Proposal Presentation / Buying Zone'
        "condition": "AND",
        "rules": [
            {"field": "f7b50a98745a1a2ec32a92d4bcfb89244fc15f4b", "type": "equals", "value": "Yes", "message": "Design Fee must be paid ('Yes')."},
            {"field": "6ee940cb2e7b5d2e1108ab76b2164771f8678558", "type": "equals", "value": "Yes", "message": "Decision-Makers for proposal must be confirmed ('Yes')."},
        ]
    },
    95: { # Rules for entering '6. Close (Card / BAMFAM)'
        "condition": "OR", # Note the OR condition here
        "rules": [
            {"field": "c61044a44d813064e799a96c88cb55bca465d04e", "type": "equals", "value": "Yes", "message": "Payment must be taken."},
            {"field": "844ec4a1daff8bcec5600224c6021aff9550c862", "type": "not_empty", "message": "Final Decision Meeting must be booked."},
        ]
    },
}

# --- Automation Fields ---
# These fields are used for automatic status changes (WON/LOST)
AUTOMATION_FIELDS = {
    "contract_signed": "0ede563fbd2d22869b5c63a15ac1f1b8e4ddf610",
    "payment_taken": "c61044a44d813064e799a96c88cb55bca465d04e",
    "loss_reason": "f7767455d77a063bc765e0b323813f513bcca2f9",
}


# Add this dictionary to sales-enforcer/config.py

# --- Milestone Ranks ---
# Points required to achieve each rank. The keys should be ordered from lowest to highest.
MILESTONES = {
    "Bronze": 1000,
    "Silver": 2500,
    "Gold": 5000,
}