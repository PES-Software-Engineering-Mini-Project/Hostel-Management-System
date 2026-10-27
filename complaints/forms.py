from django import forms

from .models import DESCRIPTION_MAX_LENGTH, Complaint


class ComplaintForm(forms.ModelForm):
    """Only category and description are typed in. Student and status are set by the view/model."""

    class Meta:
        model = Complaint
        fields = ["category", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5, "maxlength": DESCRIPTION_MAX_LENGTH})
        }
