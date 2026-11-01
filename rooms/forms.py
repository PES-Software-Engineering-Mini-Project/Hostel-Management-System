from django import forms
from django.db.models import F

from .models import Block, Room, RoomApplication


class BlockForm(forms.ModelForm):
    class Meta:
        model = Block
        fields = ["name", "number_of_floors"]


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = [
            "block",
            "room_number",
            "floor",
            "room_type",
            "capacity",
            "monthly_fee",
        ]


class RoomApplicationForm(forms.ModelForm):
    class Meta:
        model = RoomApplication
        fields = ["preferred_block", "preferred_room_type"]
        labels = {
            "preferred_block": "Preferred Block (optional)",
            "preferred_room_type": "Preferred Room Type (optional)",
        }
        widgets = {
            "preferred_block": forms.Select(
                attrs={"class": "form-control"}
            ),
            "preferred_room_type": forms.Select(
                attrs={"class": "form-control"}
            ),
        }


class RoomFilterForm(forms.Form):
    """GET filters for the room list (FR-9.2). Blank means "any"."""

    class Status:
        AVAILABLE = "available"
        FULL = "full"
        EMPTY = "empty"
        CHOICES = [("", "Any status"), (AVAILABLE, "Has a free bed"), (FULL, "Full"), (EMPTY, "Empty")]

    block = forms.ModelChoiceField(
        queryset=Block.objects.all(), required=False, empty_label="Any block"
    )
    floor = forms.IntegerField(required=False, min_value=0)
    room_type = forms.ChoiceField(
        choices=[("", "Any type"), *Room.RoomType.choices], required=False, label="Type"
    )
    status = forms.ChoiceField(choices=Status.CHOICES, required=False)

    def filter(self, rooms):
        # Invalid values are dropped from cleaned_data, so they are ignored, not crashed on.
        self.is_valid()
        data = getattr(self, "cleaned_data", {})
        if data.get("block"):
            rooms = rooms.filter(block=data["block"])
        if data.get("floor") is not None:
            rooms = rooms.filter(floor=data["floor"])
        if data.get("room_type"):
            rooms = rooms.filter(room_type=data["room_type"])
        status = data.get("status")
        if status == self.Status.AVAILABLE:
            rooms = rooms.filter(occupied_count__lt=F("capacity"))
        elif status == self.Status.FULL:
            rooms = rooms.filter(occupied_count__gte=F("capacity"))
        elif status == self.Status.EMPTY:
            rooms = rooms.filter(occupied_count=0)
        return rooms

    @property
    def is_filtering(self):
        return any(self.data.get(name) for name in self.fields)
