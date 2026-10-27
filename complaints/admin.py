from django.contrib import admin

from .models import Complaint


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ("student", "category", "status", "raised_at")
    list_filter = ("status", "category")
    search_fields = ("student__srn", "student__first_name", "student__last_name", "description")
    # Status is read-only here so the Django admin cannot skip the Open -> In Progress ->
    # Resolved workflow; the HMS pages move it with Complaint.change_status().
    readonly_fields = ("status", "raised_at", "updated_at")
