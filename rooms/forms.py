
from django import forms
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
