from django.db import models

from accounts.models import Business
from invoices.models import Invoice


class ReconciliationRun(models.Model):
    STATUS_CHOICES = [
        ("processing", "Processing"),
        ("done", "Done"),
        ("failed", "Failed"),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="runs")
    period = models.CharField(max_length=7, blank=True)  # "MM-YYYY"
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="processing")
    error_message = models.CharField(max_length=500, blank=True)

    total_books_invoices = models.PositiveIntegerField(default=0)
    total_statement_invoices = models.PositiveIntegerField(default=0)
    matched_count = models.PositiveIntegerField(default=0)
    flagged_count = models.PositiveIntegerField(default=0)
    itc_at_risk_value = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class Discrepancy(models.Model):
    TYPE_CHOICES = [
        ("matched", "Matched"),
        ("missing_in_2a", "Missing in GSTR-2A/2B"),
        ("missing_in_books", "Missing in Purchase Register"),
        ("value_mismatch", "Value Mismatch"),
        ("duplicate", "Duplicate"),
        ("gstin_mismatch", "GSTIN Mismatch"),
        ("date_mismatch", "Date Mismatch"),
        ("fuzzy_match", "Possible Fuzzy Match"),
    ]
    REVIEW_STATUS_CHOICES = [
        ("open", "Open"),
        ("in_review", "In Review"),
        ("supplier_contacted", "Supplier Contacted"),
        ("resolved", "Resolved"),
        ("ignored", "Ignored"),
    ]

    run = models.ForeignKey(ReconciliationRun, on_delete=models.CASCADE, related_name="discrepancies")
    discrepancy_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    books_invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    statement_invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    detail = models.CharField(max_length=500, blank=True)
    ai_explanation = models.TextField(blank=True)
    confidence_score = models.PositiveSmallIntegerField(default=100)
    risk_score = models.PositiveSmallIntegerField(default=0)
    risk_level = models.CharField(max_length=10, default="low")
    review_status = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default="open")
    resolution_note = models.TextField(blank=True)
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "discrepancies"
        indexes = [models.Index(fields=["run", "discrepancy_type"])]

    @property
    def value_at_risk(self):
        inv = self.books_invoice or self.statement_invoice
        if inv is None or self.discrepancy_type == "matched":
            return 0
        return inv.tax_amount


class DiscrepancyAuditEvent(models.Model):
    discrepancy = models.ForeignKey(Discrepancy, on_delete=models.CASCADE, related_name="audit_events")
    actor = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50)
    detail = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
