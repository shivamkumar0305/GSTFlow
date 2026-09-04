from django.contrib import admin

from .models import Invoice, InvoiceBatch

admin.site.register(InvoiceBatch)
admin.site.register(Invoice)
