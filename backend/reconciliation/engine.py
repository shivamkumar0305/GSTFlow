"""Deterministic, rule-based invoice reconciliation engine.

This module is intentionally plain Python: no Django imports, no I/O, no LLM
calls. It takes two lists of invoice records (from the business's own
purchase register, and from the GSTR-2A/2B statement) and returns a list of
match results. This keeps the actual reconciliation logic reproducible and
unit-testable in isolation, and auditable/explainable on its own — the AI
layer (reconciliation/ai_explain.py) only ever narrates results this engine
already produced; it never decides them.

An invoice record is a dict with keys:
    id, supplier_gstin, invoice_number, invoice_date, taxable_value, tax_amount

`taxable_value`/`tax_amount` should be Decimal or float; `invoice_date` a
`date` or None.
"""

from dataclasses import dataclass
from decimal import Decimal

MATCHED = "matched"
MISSING_IN_2A = "missing_in_2a"
MISSING_IN_BOOKS = "missing_in_books"
VALUE_MISMATCH = "value_mismatch"
DUPLICATE = "duplicate"
GSTIN_MISMATCH = "gstin_mismatch"
DATE_MISMATCH = "date_mismatch"
FUZZY_MATCH = "fuzzy_match"

DEFAULT_VALUE_TOLERANCE = Decimal("1.00")
GSTIN_MAX_EDIT_DISTANCE = 2


@dataclass
class MatchResult:
    discrepancy_type: str
    books_invoice_id: int | None
    statement_invoice_id: int | None
    detail: str = ""
    confidence_score: int = 100


def _invoice_value(rec: dict) -> Decimal:
    return Decimal(str(rec.get("taxable_value") or 0)) + Decimal(str(rec.get("tax_amount") or 0))


def _norm_invoice_number(value: str) -> str:
    return "".join(ch for ch in str(value).upper().strip() if ch.isalnum())


def _key(rec: dict) -> tuple[str, str]:
    return (str(rec.get("supplier_gstin", "")).upper().strip(), _norm_invoice_number(rec.get("invoice_number", "")))


def _edit_distance(a: str, b: str) -> int:
    """Standard Levenshtein distance, small-input only (GSTINs are 15 chars)."""
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[-1]


def _similarity(a: str, b: str) -> float:
    """Normalized edit-distance similarity for short invoice/GSTIN strings."""
    a, b = str(a or ""), str(b or "")
    if not a and not b:
        return 1.0
    return max(0.0, 1 - (_edit_distance(a, b) / max(len(a), len(b), 1)))


def _fuzzy_confidence(book_rec: dict, stmt_rec: dict) -> int:
    """Conservative, deterministic confidence score for a review candidate.

    Invoice number carries most of the weight; GSTIN, value and date provide
    corroborating evidence. Candidates must clear a high threshold before they
    are shown to a reviewer.
    """
    invoice_similarity = _similarity(
        _norm_invoice_number(book_rec.get("invoice_number", "")),
        _norm_invoice_number(stmt_rec.get("invoice_number", "")),
    )
    gstin_similarity = _similarity(book_rec.get("supplier_gstin", ""), stmt_rec.get("supplier_gstin", ""))
    book_value, stmt_value = _invoice_value(book_rec), _invoice_value(stmt_rec)
    value_similarity = max(0.0, 1 - float(abs(book_value - stmt_value) / max(book_value, stmt_value, Decimal("1"))))
    dates_match = bool(
        book_rec.get("invoice_date")
        and stmt_rec.get("invoice_date")
        and book_rec["invoice_date"] == stmt_rec["invoice_date"]
    )
    score = invoice_similarity * 55 + gstin_similarity * 20 + value_similarity * 20 + (5 if dates_match else 0)
    return round(score)


def _find_duplicates(records: list[dict]) -> tuple[dict[tuple, dict], list[MatchResult]]:
    """Groups records by (gstin, invoice_number). Keeps the first occurrence
    of each key for matching; every later occurrence is flagged DUPLICATE."""
    by_key: dict[tuple, dict] = {}
    duplicates: list[MatchResult] = []
    for rec in records:
        key = _key(rec)
        if key in by_key:
            duplicates.append(
                MatchResult(
                    discrepancy_type=DUPLICATE,
                    books_invoice_id=rec["id"] if rec["source"] == "books" else None,
                    statement_invoice_id=rec["id"] if rec["source"] == "2a" else None,
                    detail=(
                        f"Duplicate of invoice {rec['invoice_number']} from supplier "
                        f"{rec['supplier_gstin']} already present in this upload."
                    ),
                )
            )
        else:
            by_key[key] = rec
    return by_key, duplicates


def reconcile(
    books_records: list[dict],
    statement_records: list[dict],
    value_tolerance: Decimal = DEFAULT_VALUE_TOLERANCE,
) -> list[MatchResult]:
    """Reconciles a purchase register against a GSTR-2A/2B statement.

    Matching key is (supplier GSTIN, normalized invoice number). Within-source
    duplicates are flagged first; the remaining unique-keyed records are then
    matched exactly, then a fuzzy pass looks for likely GSTIN typos among
    what's left unmatched on both sides (same invoice number + value, GSTIN
    off by a couple of characters).
    """
    value_tolerance = Decimal(str(value_tolerance))

    books_by_key, book_dupes = _find_duplicates(books_records)
    stmt_by_key, stmt_dupes = _find_duplicates(statement_records)

    results: list[MatchResult] = [*book_dupes, *stmt_dupes]

    books_keys = set(books_by_key)
    stmt_keys = set(stmt_by_key)

    for key in books_keys & stmt_keys:
        book_rec = books_by_key[key]
        stmt_rec = stmt_by_key[key]
        diff = abs(_invoice_value(book_rec) - _invoice_value(stmt_rec))
        if diff > value_tolerance:
            results.append(
                MatchResult(
                    discrepancy_type=VALUE_MISMATCH,
                    books_invoice_id=book_rec["id"],
                    statement_invoice_id=stmt_rec["id"],
                    detail=(
                        f"Books show invoice value {_invoice_value(book_rec)} but GSTR-2A/2B shows "
                        f"{_invoice_value(stmt_rec)} (difference of {diff})."
                    ),
                    confidence_score=95,
                )
            )
        elif (
            book_rec.get("invoice_date")
            and stmt_rec.get("invoice_date")
            and book_rec["invoice_date"] != stmt_rec["invoice_date"]
        ):
            results.append(
                MatchResult(
                    discrepancy_type=DATE_MISMATCH,
                    books_invoice_id=book_rec["id"],
                    statement_invoice_id=stmt_rec["id"],
                    detail=(
                        f"Invoice date in books ({book_rec['invoice_date']}) does not match "
                        f"GSTR-2A/2B ({stmt_rec['invoice_date']})."
                    ),
                )
            )
        else:
            results.append(
                MatchResult(
                    discrepancy_type=MATCHED,
                    books_invoice_id=book_rec["id"],
                    statement_invoice_id=stmt_rec["id"],
                )
            )

    unmatched_book_keys = books_keys - stmt_keys
    unmatched_stmt_keys = stmt_keys - books_keys

    # Fuzzy pass: same invoice number + value within tolerance, GSTIN differs
    # by only a couple of characters (likely a typo, not a genuinely
    # different/missing invoice).
    consumed_book_keys: set = set()
    consumed_stmt_keys: set = set()
    for bkey in unmatched_book_keys:
        book_rec = books_by_key[bkey]
        for skey in unmatched_stmt_keys - consumed_stmt_keys:
            stmt_rec = stmt_by_key[skey]
            if bkey[1] != skey[1]:  # invoice numbers must match
                continue
            if abs(_invoice_value(book_rec) - _invoice_value(stmt_rec)) > value_tolerance:
                continue
            if _edit_distance(bkey[0], skey[0]) > GSTIN_MAX_EDIT_DISTANCE:
                continue
            results.append(
                MatchResult(
                    discrepancy_type=GSTIN_MISMATCH,
                    books_invoice_id=book_rec["id"],
                    statement_invoice_id=stmt_rec["id"],
                    detail=(
                        f"Invoice {book_rec['invoice_number']} matches on number and value, but the "
                        f"supplier GSTIN differs: books show {bkey[0]}, GSTR-2A/2B shows {skey[0]}."
                    ),
                )
            )
            consumed_book_keys.add(bkey)
            consumed_stmt_keys.add(skey)
            break

    # Second fuzzy pass: invoice-number variants or close values with enough
    # supporting evidence become reviewable suggestions, never auto-matches.
    for bkey in unmatched_book_keys - consumed_book_keys:
        book_rec = books_by_key[bkey]
        candidates = []
        for skey in unmatched_stmt_keys - consumed_stmt_keys:
            stmt_rec = stmt_by_key[skey]
            gstin_similarity = _similarity(book_rec.get("supplier_gstin", ""), stmt_rec.get("supplier_gstin", ""))
            if gstin_similarity < 0.6:
                continue
            confidence = _fuzzy_confidence(book_rec, stmt_rec)
            if confidence >= 80:
                candidates.append((confidence, skey, stmt_rec))
        if not candidates:
            continue
        confidence, skey, stmt_rec = max(candidates, key=lambda item: item[0])
        results.append(
            MatchResult(
                discrepancy_type=FUZZY_MATCH,
                books_invoice_id=book_rec["id"],
                statement_invoice_id=stmt_rec["id"],
                detail=(
                    f"Possible match: books invoice {book_rec['invoice_number']} and GSTR-2A/2B invoice "
                    f"{stmt_rec['invoice_number']} have a {confidence}% similarity score. Review before accepting."
                ),
                confidence_score=confidence,
            )
        )
        consumed_book_keys.add(bkey)
        consumed_stmt_keys.add(skey)

    for bkey in unmatched_book_keys - consumed_book_keys:
        book_rec = books_by_key[bkey]
        results.append(
            MatchResult(
                discrepancy_type=MISSING_IN_2A,
                books_invoice_id=book_rec["id"],
                statement_invoice_id=None,
                detail=(
                    f"Invoice {book_rec['invoice_number']} from {book_rec['supplier_gstin']} is in your "
                    f"purchase register but not in the GSTR-2A/2B statement — ITC may be at risk."
                ),
            )
        )

    for skey in unmatched_stmt_keys - consumed_stmt_keys:
        stmt_rec = stmt_by_key[skey]
        results.append(
            MatchResult(
                discrepancy_type=MISSING_IN_BOOKS,
                books_invoice_id=None,
                statement_invoice_id=stmt_rec["id"],
                detail=(
                    f"Invoice {stmt_rec['invoice_number']} from {stmt_rec['supplier_gstin']} appears in "
                    f"the GSTR-2A/2B statement but was not found in your purchase register."
                ),
            )
        )

    return results
