
from django.contrib import admin
from .models import Room, RoomAllocation, FeeRecord, RoomApplication


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("room_number", "capacity")
    search_fields = ("room_number",)


@admin.register(RoomAllocation)
class RoomAllocationAdmin(admin.ModelAdmin):
    list_display = ("student", "room", "is_active")
    list_filter = ("is_active",)
    search_fields = ("student__username", "room__room_number")


@admin.register(FeeRecord)
class FeeRecordAdmin(admin.ModelAdmin):
    list_display = ("student", "amount_due", "amount_paid")
    search_fields = ("student__username",)


@admin.register(RoomApplication)
class RoomApplicationAdmin(admin.ModelAdmin):
    list_display = ("student", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("student__username",)
