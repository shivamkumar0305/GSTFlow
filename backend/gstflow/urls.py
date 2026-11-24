from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from reconciliation.views import DashboardView


def healthcheck(_request):
    return JsonResponse({"status": "ok"})

urlpatterns = [
    path("healthz/", healthcheck, name="healthcheck"),
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/uploads/", include("invoices.urls")),
    path("api/reconcile/", include("reconciliation.urls")),
    path("api/dashboard/", DashboardView.as_view(), name="dashboard"),
]
