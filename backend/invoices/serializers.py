from rest_framework import serializers

from .models import Invoice, InvoiceBatch


class InvoiceBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceBatch
        fields = [
            "id",
            "source",
            "original_filename",
            "period",
            "status",
            "error_message",
            "row_count",
            "uploaded_at",
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    invoice_value = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "source",
            "supplier_gstin",
            "supplier_name",
            "invoice_number",
            "invoice_date",
            "taxable_value",
            "tax_amount",
            "invoice_value",
        ]
