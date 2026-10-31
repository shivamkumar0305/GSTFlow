"""Deterministic discrepancy risk scoring used for prioritization."""

from decimal import Decimal


TYPE_BASE_SCORES = {
    "missing_in_2a": 65,
    "missing_in_books": 50,
    "value_mismatch": 55,
    "duplicate": 45,
    "gstin_mismatch": 60,
    "date_mismatch": 35,
    "fuzzy_match": 40,
}


def score_discrepancy(discrepancy_type: str, tax_amount: Decimal | int | float, confidence_score: int = 100) -> tuple[int, str]:
    """Return a reproducible 0-100 score and low/medium/high priority label."""
    score = TYPE_BASE_SCORES.get(discrepancy_type, 25)
    tax = Decimal(str(tax_amount or 0))
    if tax >= 100000:
        score += 25
    elif tax >= 25000:
        score += 15
    elif tax >= 5000:
        score += 8
    if discrepancy_type == "fuzzy_match" and confidence_score < 90:
        score += 10
    score = min(score, 100)
    level = "high" if score >= 75 else "medium" if score >= 45 else "low"
    return score, level
