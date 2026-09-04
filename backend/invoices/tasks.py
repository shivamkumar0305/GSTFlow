from decimal import Decimal

from celery import shared_task
from django.core.cache import cache

from . import parsing
from .models import Invoice, InvoiceBatch

UPLOAD_CACHE_PREFIX = "upload"


def _key(token: str, name: str) -> str:
    return f"{UPLOAD_CACHE_PREFIX}:{token}:{name}"


def _bump_attempts(token: str) -> int:
    attempts = cache.get(_key(token, "attempts"), 0) + 1
    cache.set(_key(token, "attempts"), attempts, timeout=None)
    return attempts


@shared_task
def parse_and_store_batch(batch_id: int, upload_token: str, source: str):
    batch = InvoiceBatch.objects.select_related("business").get(id=batch_id)
    file_bytes = cache.get(_key(upload_token, "bytes"))
    filename = cache.get(_key(upload_token, "filename"))
    password = cache.get(_key(upload_token, "pw"))
    # Discard the plaintext password immediately after reading it — never
    # keep it around longer than this task needs it.
    cache.delete(_key(upload_token, "pw"))

    if file_bytes is None or filename is None:
        batch.status = "failed"
        batch.error_message = "Upload expired before it could be processed. Please re-upload."
        batch.save(update_fields=["status", "error_message"])
        return

    try:
        rows = parsing.parse_tabular_file(file_bytes, filename, password)
    except parsing.FileNeedsPassword:
        _bump_attempts(upload_token)
        batch.status = "failed"
        batch.error_message = "This file needs a password (or the password given was incorrect)."
        batch.save(update_fields=["status", "error_message"])
        return
    except parsing.InvalidFile as exc:
        batch.status = "failed"
        batch.error_message = str(exc)
        batch.save(update_fields=["status", "error_message"])
        return

    objs = [
        Invoice(
            business=batch.business,
            batch=batch,
            source=source,
            supplier_gstin=row["supplier_gstin"],
            supplier_name=row["supplier_name"],
            invoice_number=row["invoice_number"],
            invoice_date=row["invoice_date"],
            taxable_value=Decimal(str(row["taxable_value"])),
            tax_amount=Decimal(str(row["tax_amount"])),
        )
        for row in rows
    ]
    Invoice.objects.bulk_create(objs, batch_size=500)

    batch.row_count = len(objs)
    batch.status = "done"
    batch.save(update_fields=["row_count", "status"])

    cache.delete(_key(upload_token, "bytes"))
    cache.delete(_key(upload_token, "filename"))
    cache.delete(_key(upload_token, "attempts"))
