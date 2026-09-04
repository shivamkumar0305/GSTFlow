"""AI-generated plain-language explanations for reconciliation discrepancies.

This is the ONLY place in the codebase an LLM is called. The reconciliation
engine (reconciliation/engine.py) has already deterministically decided what
each discrepancy *is* by the time anything here runs — this module just
narrates that decision in plain language for a non-accountant reader. It
never decides match outcomes.

Kept isolated and swappable: everything below the model call itself is
plain string formatting, and `explain_discrepancy` is the one function the
rest of the codebase calls.
"""

import logging
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)

_TEMPLATES = {
    "matched": "This invoice matches cleanly between your books and the GSTR-2A/2B statement. No action needed.",
    "missing_in_2a": (
        "This invoice is in your purchase register but your supplier hasn't reported it in their GST "
        "return yet, so it doesn't appear in your GSTR-2A/2B. Until they file it, you may not be able to "
        "claim input tax credit (ITC) on this invoice. Follow up with the supplier to confirm they've "
        "filed their GSTR-1 for this period."
    ),
    "missing_in_books": (
        "This invoice shows up in your GSTR-2A/2B statement (meaning your supplier reported it) but it's "
        "not in your purchase register. Check whether this purchase was recorded under a different "
        "invoice number, or whether it's a genuine invoice you missed booking."
    ),
    "value_mismatch": (
        "This invoice exists on both sides but the amounts don't match. That usually means a typo during "
        "data entry, a credit/debit note that hasn't been accounted for, or a rounding difference. Verify "
        "the original invoice to see which figure is correct."
    ),
    "duplicate": (
        "This invoice number appears more than once in the same upload. Either the same purchase was "
        "recorded twice, or two different invoices were accidentally given the same number — double-check "
        "before claiming ITC twice on the same purchase."
    ),
    "gstin_mismatch": (
        "The invoice number and amount match, but the supplier's GSTIN is slightly different between your "
        "books and the GSTR-2A/2B statement. This is usually a data-entry typo rather than a different "
        "supplier — compare both GSTINs character by character to confirm."
    ),
    "date_mismatch": (
        "This invoice matches on number and amount, but the invoice date differs between your books and "
        "the GSTR-2A/2B statement. This can shift which return period the ITC belongs to — confirm the "
        "correct date against the physical/PDF invoice."
    ),
}


def _fallback_explanation(discrepancy_type: str, detail: str) -> str:
    base = _TEMPLATES.get(discrepancy_type, "This item needs manual review.")
    return f"{base} ({detail})" if detail else base


def explain_discrepancy(discrepancy_type: str, detail: str, context: dict) -> str:
    """Returns a plain-language explanation for one discrepancy.

    `context` carries whatever fields are useful for the prompt (GSTIN,
    invoice number, amounts on each side, dates) — purely descriptive data
    already produced by the reconciliation engine.
    """
    if not settings.AI_EXPLANATIONS_ENABLED or not settings.GROQ_API_KEY:
        return _fallback_explanation(discrepancy_type, detail)

    try:
        payload = {
            "model": settings.GROQ_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You explain GST invoice reconciliation discrepancies to small business "
                        "owners who are not accountants. Be concise, plain-language, practical, "
                        "and do not invent figures beyond the given data."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Discrepancy type: {discrepancy_type}\n"
                        f"Rule-engine detail: {detail}\n"
                        f"Data: {context}\n\n"
                        "Write 2-3 short sentences explaining what happened and what to check next."
                    ),
                },
            ],
            "temperature": 0.2,
            "max_tokens": 200,
        }
        request = Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except (HTTPError, URLError, KeyError, IndexError, json.JSONDecodeError, TimeoutError):
        logger.exception("Groq explanation call failed for discrepancy_type=%s; using fallback", discrepancy_type)
        return _fallback_explanation(discrepancy_type, detail)
