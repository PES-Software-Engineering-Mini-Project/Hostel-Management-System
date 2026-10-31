
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.urls import reverse

from .models import Block, Room


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("name", "number_of_floors")
    search_fields = ("name",)

    def save_model(self, request, obj, form, change):
        try:
            obj.full_clean()
        except ValidationError as error:
            form.add_error(None, error)
            raise
        super().save_model(request, obj, form, change)


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

    # occupied_count is visible but cannot be edited from the list.
    # It is also excluded from list_editable.

    def delete_model(self, request, obj):
        if obj.occupied_count > 0:
            self.message_user(
                request,
                "Occupied rooms cannot be deleted. Reallocate "
                "their occupants first.",
                level=messages.ERROR,
            )
            return

        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        if queryset.filter(occupied_count__gt=0).exists():
            self.message_user(
                request,
                "Selected rooms include occupied rooms. "
                "No rooms were deleted.",
                level=messages.ERROR,
            )
            return

        queryset.delete()
        self.message_user(
            request,
            "Selected rooms were deleted successfully.",
            level=messages.SUCCESS,
        )

    def delete_view(self, request, object_id, extra_context=None):
        obj = self.get_object(request, object_id)

        if (
            obj is not None
            and obj.occupied_count > 0
            and request.method == "POST"
        ):
            self.message_user(
                request,
                "Occupied rooms cannot be deleted. Reallocate "
                "their occupants first.",
                level=messages.ERROR,
            )
            return redirect(
                reverse("admin:rooms_room_changelist")
            )

        return super().delete_view(
            request,
            object_id,
            extra_context=extra_context,
        )
