from django.contrib import admin

from .models import Discrepancy, ReconciliationRun

admin.site.register(ReconciliationRun)
admin.site.register(Discrepancy)
