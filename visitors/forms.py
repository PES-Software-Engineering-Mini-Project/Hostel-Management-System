from django import forms

from .models import PURPOSE_MAX_LENGTH, Visitor


class VisitorForm(forms.ModelForm):
    """Only the visitor's details are typed in. Host and entry time are set by the
    view/model, never by the browser (NFR-3, FR-7.2)."""

    class Meta:
        model = Visitor
        fields = ["name", "contact_number", "purpose"]
        widgets = {
            "purpose": forms.Textarea(attrs={"rows": 3, "maxlength": PURPOSE_MAX_LENGTH})
        }


class VisitorFilterForm(forms.Form):
    """GET filter for the admin visitor list (FR-7.4). Blank means "all"."""

    PRESENCE_CHOICES = [
        ("", "All visitors"),
        ("inside", "Currently inside"),
        ("checked_out", "Checked out"),
    ]

    presence = forms.ChoiceField(choices=PRESENCE_CHOICES, required=False)

    def filter(self, visitors):
        # Invalid values are dropped from cleaned_data, so they are ignored, not crashed on.
        self.is_valid()
        data = getattr(self, "cleaned_data", {})
        if data.get("presence") == "inside":
            visitors = visitors.filter(exit_time__isnull=True)
        elif data.get("presence") == "checked_out":
            visitors = visitors.filter(exit_time__isnull=False)
        return visitors

    @property
    def is_filtering(self):
        return any(self.data.get(name) for name in self.fields)
