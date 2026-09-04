from django.contrib import admin
from django.urls import include, path

from reconciliation.views import DashboardView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/uploads/", include("invoices.urls")),
    path("api/reconcile/", include("reconciliation.urls")),
    path("api/dashboard/", DashboardView.as_view(), name="dashboard"),
]
