from django import forms
from django.conf import settings

from .models import FeeRecord, Payment


class StudentChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        room = obj.room_allocation.room
        return f"{obj.srn} - {obj.get_full_name()} ({room.block.name} {room.room_number})"


class FeeRecordForm(forms.ModelForm):
    """Create a term's fee record; the amount due comes from the allotted room (FR-5.1)."""

    class Meta:
        model = FeeRecord
        fields = ["student", "term"]
        field_classes = {"student": StudentChoiceField}
        help_texts = {
            "student": "Only students with an allotted room are listed. The fee due is "
            f"the room's monthly fee × {settings.HMS_MONTHS_PER_TERM} months.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = (
            self.fields["student"]
            .queryset.filter(room_allocation__isnull=False)
            .select_related("room_allocation__room__block")
            .order_by("srn")
        )
        self.fields["student"].error_messages["invalid_choice"] = (
            "Choose a student who has an allotted room."
        )

    def clean_term(self):
        return " ".join(self.cleaned_data["term"].split())

    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get("student")
        term = cleaned_data.get("term")
        if student and term and FeeRecord.objects.filter(student=student, term__iexact=term).exists():
            self.add_error("term", "This student already has a fee record for this term.")
        if student and not self.has_error("student"):
            room = student.room_allocation.room
            amount_due = FeeRecord.term_fee_for(room)
            if amount_due <= 0:
                self.add_error(
                    "student", f"Room {room.room_number} has no monthly fee set, so no fee is due."
                )
            else:
                self.instance.room = room
                self.instance.amount_due = amount_due
        return cleaned_data


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["amount", "paid_on"]
        labels = {"amount": "Amount (₹)", "paid_on": "Payment date"}
        widgets = {"paid_on": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, fee_record, recorded_by, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.fee_record = fee_record
        self.instance.recorded_by = recorded_by
