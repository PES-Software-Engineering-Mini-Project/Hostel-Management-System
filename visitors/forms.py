from django import forms
from django.db.models import Q

from .models import Visitor


class VisitorForm(forms.ModelForm):
    """Only what the visitor gives is typed. Host and times are set by the view/model."""

    class Meta:
        model = Visitor
        fields = ["name", "phone", "purpose"]


class VisitorFilterForm(forms.Form):
    """GET filters for the admin visitor log (FR-7.4). Blank means "any"."""

    STATUS_CHOICES = [("", "Any"), ("inside", "On premises"), ("left", "Checked out")]

    q = forms.CharField(label="Visitor or host", required=False)
    status = forms.ChoiceField(choices=STATUS_CHOICES, required=False)

    def filter(self, visitors):
        self.is_valid()
        data = getattr(self, "cleaned_data", {})
        if data.get("status") == "inside":
            visitors = visitors.filter(exited_at__isnull=True)
        elif data.get("status") == "left":
            visitors = visitors.filter(exited_at__isnull=False)
        q = (data.get("q") or "").strip()
        if q:
            visitors = visitors.filter(
                Q(name__icontains=q)
                | Q(host__srn__icontains=q)
                | Q(host__first_name__icontains=q)
                | Q(host__last_name__icontains=q)
            )
        return visitors

    @property
    def is_filtering(self):
        return any(self.data.get(name) for name in self.fields)
