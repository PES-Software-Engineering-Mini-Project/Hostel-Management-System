from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class HMSUserAdmin(UserAdmin):
    model = User
    ordering = ("srn",)
    list_display = ("srn", "email", "first_name", "last_name", "role", "is_staff")
    fieldsets = UserAdmin.fieldsets + (
        ("HMS identity", {"fields": ("srn", "contact_number", "branch", "year_of_study", "role")} ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("HMS identity", {"fields": ("srn", "email", "contact_number", "branch", "year_of_study", "role")} ),
    )
