from django.contrib import admin

from .models import Visitor


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ("name", "host", "entered_at", "exited_at")
    search_fields = ("name", "host__srn")
    readonly_fields = ("entered_at", "exited_at")
