
from django import forms

from .models import Block, Room


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
