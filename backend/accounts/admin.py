from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Business, User


class UserAdmin(BaseUserAdmin):
    ordering = ["email"]


admin.site.register(User, UserAdmin)
admin.site.register(Business)
