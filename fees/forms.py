from django import forms

from .models import FeeRecord, Payment


class StudentChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.srn} - {obj.get_full_name()}"


class FeeRecordForm(forms.ModelForm):
    class Meta:
        model = FeeRecord
        fields = ["student", "term", "amount_due"]
        field_classes = {"student": StudentChoiceField}
        labels = {"amount_due": "Amount due (₹)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = self.fields["student"].queryset.order_by("srn")

    def clean_term(self):
        return " ".join(self.cleaned_data["term"].split())

    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get("student")
        term = cleaned_data.get("term")
        if student and term and FeeRecord.objects.filter(student=student, term__iexact=term).exists():
            self.add_error("term", "This student already has a fee record for this term.")
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
