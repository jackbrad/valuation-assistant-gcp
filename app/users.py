"""Demo users. # DEMO-SHORTCUT: production uses IAP + Google identity, roles from groups."""

USERS = {
    "alex.reviewer": {"name": "Alex Vance", "role": "Senior Reviewer", "has_stake": False},
    "jordan.lo": {"name": "Jordan Lee", "role": "Loan Officer", "has_stake": True},
    "sam.reviewer": {"name": "Sam Taylor", "role": "Appraisal Reviewer", "has_stake": False},
    "pat.steward": {"name": "Pat Martinez", "role": "Data Steward", "has_stake": False},
}


def name(uid: str) -> str:
    if uid == "pipeline_g1":
        return "the automatic data check"
    return USERS.get(uid, {}).get("name", uid)
