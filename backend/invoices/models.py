from django.db import models

from accounts.models import Business


class InvoiceBatch(models.Model):
    """One uploaded file (purchase register or GSTR-2A/2B statement)."""

    SOURCE_CHOICES = [("books", "Purchase Register"), ("2a", "GSTR-2A/2B")]
    STATUS_CHOICES = [
        ("processing", "Processing"),
        ("done", "Done"),
        ("failed", "Failed"),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="batches")
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES)
    original_filename = models.CharField(max_length=255)
    period = models.CharField(max_length=7, blank=True)  # "MM-YYYY"
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="processing")
    error_message = models.CharField(max_length=500, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)


class Invoice(models.Model):
    """A single invoice row, either from the business's own books or the
    GSTR-2A/2B statement, distinguished by `source`."""

    SOURCE_CHOICES = [("books", "Purchase Register"), ("2a", "GSTR-2A/2B")]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="invoices")
    batch = models.ForeignKey(InvoiceBatch, on_delete=models.CASCADE, related_name="invoices")
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES)

    supplier_gstin = models.CharField(max_length=15)
    supplier_name = models.CharField(max_length=255, blank=True)
    invoice_number = models.CharField(max_length=50)
    invoice_date = models.DateField(null=True, blank=True)
    taxable_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["business", "source", "supplier_gstin", "invoice_number"]),
        ]

    def __str__(self):
        return f"{self.source}:{self.supplier_gstin}:{self.invoice_number}"

    @property
    def invoice_value(self):
        return self.taxable_value + self.tax_amount
