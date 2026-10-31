from celery import shared_task
from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from invoices.models import Invoice, InvoiceBatch

from . import engine
from .ai_explain import explain_discrepancy
from .models import Discrepancy, DiscrepancyAuditEvent, ReconciliationRun
from .risk import score_discrepancy

# Discrepancy types worth spending an AI call on. "matched" needs no
# explanation; everything else benefits from a plain-language note.
EXPLAINABLE_TYPES = {
    engine.MISSING_IN_2A,
    engine.MISSING_IN_BOOKS,
    engine.VALUE_MISMATCH,
    engine.DUPLICATE,
    engine.GSTIN_MISMATCH,
    engine.DATE_MISMATCH,
    engine.FUZZY_MATCH,
}


def _to_record(inv: Invoice) -> dict:
    return {
        "id": inv.id,
        "supplier_gstin": inv.supplier_gstin,
        "invoice_number": inv.invoice_number,
        "invoice_date": inv.invoice_date,
        "taxable_value": inv.taxable_value,
        "tax_amount": inv.tax_amount,
        "source": inv.source,
    }


@shared_task
def run_reconciliation(run_id: int):
    run = ReconciliationRun.objects.get(id=run_id)

    # Scope to the single latest successfully-parsed batch per source for
    # this period, not by each invoice's own date (GSTR-2A entries
    # legitimately carry dates outside the filing month — that's exactly
    # what date_mismatch is for) and not to every batch ever uploaded under
    # this period (a re-upload should supersede the previous one, not pile
    # up alongside it and get flagged as duplicates against itself).
    books_batch = (
        InvoiceBatch.objects.filter(
            business=run.business, source="books", period=run.period, status="done"
        )
        .order_by("-uploaded_at")
        .first()
    )
    stmt_batch = (
        InvoiceBatch.objects.filter(
            business=run.business, source="2a", period=run.period, status="done"
        )
        .order_by("-uploaded_at")
        .first()
    )

    if not books_batch or not stmt_batch:
        run.status = "failed"
        run.error_message = (
            f"No completed upload found for period {run.period!r} on "
            f"{'the purchase register' if not books_batch else 'the GSTR-2A/2B statement'}."
        )
        run.save(update_fields=["status", "error_message"])
        return

    books_qs = Invoice.objects.filter(batch=books_batch)
    stmt_qs = Invoice.objects.filter(batch=stmt_batch)

    books_records = [_to_record(i) for i in books_qs]
    stmt_records = [_to_record(i) for i in stmt_qs]

    invoices_by_id = {i.id: i for i in list(books_qs) + list(stmt_qs)}

    try:
        results = engine.reconcile(
            books_records, stmt_records, value_tolerance=settings.RECONCILIATION_VALUE_TOLERANCE
        )
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        run.save(update_fields=["status", "error_message"])
        return

    discrepancy_objs = []
    matched_count = 0
    flagged_count = 0
    itc_at_risk = 0

    for result in results:
        if result.discrepancy_type == engine.MATCHED:
            matched_count += 1
            continue

        flagged_count += 1
        books_inv = invoices_by_id.get(result.books_invoice_id)
        stmt_inv = invoices_by_id.get(result.statement_invoice_id)
        at_risk_inv = books_inv or stmt_inv
        if at_risk_inv is not None:
            itc_at_risk += at_risk_inv.tax_amount

        risk_score, risk_level = score_discrepancy(
            result.discrepancy_type,
            at_risk_inv.tax_amount if at_risk_inv else 0,
            result.confidence_score,
        )

        ai_explanation = ""
        if result.discrepancy_type in EXPLAINABLE_TYPES:
            context = {
                "supplier_gstin": (books_inv or stmt_inv).supplier_gstin if at_risk_inv else "",
                "invoice_number": (books_inv or stmt_inv).invoice_number if at_risk_inv else "",
                "books_value": str(books_inv.invoice_value) if books_inv else None,
                "statement_value": str(stmt_inv.invoice_value) if stmt_inv else None,
            }
            ai_explanation = explain_discrepancy(result.discrepancy_type, result.detail, context)

        discrepancy_objs.append(
            Discrepancy(
                run=run,
                discrepancy_type=result.discrepancy_type,
                books_invoice_id=result.books_invoice_id,
                statement_invoice_id=result.statement_invoice_id,
                detail=result.detail,
                ai_explanation=ai_explanation,
                confidence_score=result.confidence_score,
                risk_score=risk_score,
                risk_level=risk_level,
            )
        )

    Discrepancy.objects.bulk_create(discrepancy_objs, batch_size=500)
    created_discrepancies = Discrepancy.objects.filter(run=run)
    DiscrepancyAuditEvent.objects.bulk_create(
        [
            DiscrepancyAuditEvent(
                discrepancy=discrepancy,
                action="created_by_reconciliation",
                detail="Created automatically by the reconciliation engine.",
            )
            for discrepancy in created_discrepancies
        ],
        batch_size=500,
    )

    run.total_books_invoices = len(books_records)
    run.total_statement_invoices = len(stmt_records)
    run.matched_count = matched_count
    run.flagged_count = flagged_count
    run.itc_at_risk_value = itc_at_risk
    run.status = "done"
    run.completed_at = timezone.now()
    run.save()
