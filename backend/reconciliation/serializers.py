from rest_framework import serializers

from invoices.serializers import InvoiceSerializer

from .models import Discrepancy, ReconciliationRun


class ReconciliationRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReconciliationRun
        fields = [
            "id",
            "period",
            "status",
            "error_message",
            "total_books_invoices",
            "total_statement_invoices",
            "matched_count",
            "flagged_count",
            "itc_at_risk_value",
            "created_at",
            "completed_at",
        ]


class DiscrepancySerializer(serializers.ModelSerializer):
    books_invoice = InvoiceSerializer(read_only=True)
    statement_invoice = InvoiceSerializer(read_only=True)
    value_at_risk = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Discrepancy
        fields = [
            "id",
            "discrepancy_type",
            "books_invoice",
            "statement_invoice",
            "detail",
            "ai_explanation",
            "value_at_risk",
            "resolved",
            "created_at",
        ]


class DiscrepancyResolveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discrepancy
        fields = ["resolved"]
