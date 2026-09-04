from django.db.models import Count, Sum
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from invoices.models import Invoice

from .models import Discrepancy, ReconciliationRun
from .serializers import DiscrepancyResolveSerializer, DiscrepancySerializer, ReconciliationRunSerializer
from .tasks import run_reconciliation


class TriggerReconciliationView(APIView):
    def post(self, request):
        business = request.user.business
        period = request.data.get("period", "")
        run = ReconciliationRun.objects.create(business=business, period=period, status="processing")
        run_reconciliation.delay(run.id)
        return Response(ReconciliationRunSerializer(run).data, status=202)


class ReconciliationRunDetailView(generics.RetrieveAPIView):
    serializer_class = ReconciliationRunSerializer

    def get_queryset(self):
        return ReconciliationRun.objects.filter(business=self.request.user.business)


class DiscrepancyListView(generics.ListAPIView):
    serializer_class = DiscrepancySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["discrepancy_type", "resolved"]

    def get_queryset(self):
        return Discrepancy.objects.filter(
            run_id=self.kwargs["run_id"], run__business=self.request.user.business
        ).select_related("books_invoice", "statement_invoice").order_by("discrepancy_type", "id")


class DiscrepancyResolveView(generics.UpdateAPIView):
    serializer_class = DiscrepancyResolveSerializer

    def get_queryset(self):
        return Discrepancy.objects.filter(run__business=self.request.user.business)


class DashboardView(APIView):
    def get(self, request):
        business = request.user.business
        runs = ReconciliationRun.objects.filter(business=business, status="done")
        latest_run = runs.order_by("-created_at").first()

        by_type = (
            Discrepancy.objects.filter(run__business=business, run__status="done")
            .values("discrepancy_type")
            .annotate(count=Count("id"))
        )

        return Response(
            {
                "latest_run": ReconciliationRunSerializer(latest_run).data if latest_run else None,
                "total_runs": runs.count(),
                "total_purchase_invoices": Invoice.objects.filter(business=business, source="books").count(),
                "total_statement_invoices": Invoice.objects.filter(business=business, source="2a").count(),
                "total_matched": sum(r.matched_count for r in runs),
                "total_flagged": sum(r.flagged_count for r in runs),
                "total_itc_at_risk": sum(r.itc_at_risk_value for r in runs),
                "discrepancies_by_type": {row["discrepancy_type"]: row["count"] for row in by_type},
            }
        )
