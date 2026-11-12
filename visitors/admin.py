from django.contrib import admin

from .models import Visitor


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ("name", "host", "entry_time", "exit_time")
    list_filter = ("exit_time",)
    search_fields = ("name", "host__srn", "host__first_name", "host__last_name", "purpose")
    # Times are read-only here so the Django admin cannot fake the log; the HMS
    # pages set them from the server clock (FR-7.2, FR-7.3).
    readonly_fields = ("entry_time", "exit_time")
