from django.urls import path

from .views import (
    DashboardView,
    DiscrepancyAuditListView,
    DiscrepancyListView,
    DiscrepancyResolveView,
    ReconciliationRunDetailView,
    SupplierAnalyticsView,
    TriggerReconciliationView,
)

urlpatterns = [
    path("", TriggerReconciliationView.as_view(), name="reconcile-trigger"),
    path("<int:pk>/", ReconciliationRunDetailView.as_view(), name="reconcile-detail"),
    path("<int:run_id>/discrepancies/", DiscrepancyListView.as_view(), name="reconcile-discrepancies"),
    path("discrepancies/<int:pk>/", DiscrepancyResolveView.as_view(), name="discrepancy-resolve"),
    path("discrepancies/<int:pk>/audit/", DiscrepancyAuditListView.as_view(), name="discrepancy-audit"),
    path("suppliers/", SupplierAnalyticsView.as_view(), name="supplier-analytics"),
]
