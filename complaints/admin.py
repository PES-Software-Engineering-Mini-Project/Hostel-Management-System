
from django.contrib import admin
from .models import Complaint


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = (
        "id", "student", "room", "category", "status", "created_at"
    )
    list_filter = ("status", "category", "created_at")
    search_fields = (
        "student__username",
        "room",
        "category",
        "description",
    )
