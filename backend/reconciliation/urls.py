from django.urls import path

from .views import (
    DashboardView,
    DiscrepancyListView,
    DiscrepancyResolveView,
    ReconciliationRunDetailView,
    TriggerReconciliationView,
)

urlpatterns = [
    path("", TriggerReconciliationView.as_view(), name="reconcile-trigger"),
    path("<int:pk>/", ReconciliationRunDetailView.as_view(), name="reconcile-detail"),
    path("<int:run_id>/discrepancies/", DiscrepancyListView.as_view(), name="reconcile-discrepancies"),
    path("discrepancies/<int:pk>/", DiscrepancyResolveView.as_view(), name="discrepancy-resolve"),
]
