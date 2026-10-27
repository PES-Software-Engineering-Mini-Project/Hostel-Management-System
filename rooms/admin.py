
from django.contrib import admin
from .models import Block, Room


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("name", "number_of_floors")
    search_fields = ("name",)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = (
        "room_number",
        "block",
        "floor",
        "room_type",
        "capacity",
        "occupied_count",
        "monthly_fee",
    )
    list_filter = ("block", "floor", "room_type")
    search_fields = ("room_number", "block__name")
    list_editable = ("occupied_count",)
