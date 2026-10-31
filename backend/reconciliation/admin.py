from django.contrib import admin

from .models import Discrepancy, DiscrepancyAuditEvent, ReconciliationRun

admin.site.register(ReconciliationRun)
admin.site.register(Discrepancy)
admin.site.register(DiscrepancyAuditEvent)
