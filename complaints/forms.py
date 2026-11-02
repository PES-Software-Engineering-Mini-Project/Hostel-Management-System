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


class ComplaintFilterForm(forms.Form):
    """GET filters for complaint lists (FR-9.3). Blank means "any"."""

    status = forms.ChoiceField(
        choices=[("", "Any status"), *Complaint.Status.choices], required=False
    )
    category = forms.ChoiceField(
        choices=[("", "Any category"), *Complaint.Category.choices], required=False
    )

    def filter(self, complaints):
        # Invalid values are dropped from cleaned_data, so they are ignored, not crashed on.
        self.is_valid()
        data = getattr(self, "cleaned_data", {})
        if data.get("status"):
            complaints = complaints.filter(status=data["status"])
        if data.get("category"):
            complaints = complaints.filter(category=data["category"])
        return complaints

    @property
    def is_filtering(self):
        return any(self.data.get(name) for name in self.fields)
