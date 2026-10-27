from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

MIN_AMOUNT = Decimal("0.01")
ZERO = Decimal("0.00")


class FeeRecordQuerySet(models.QuerySet):
    def with_totals(self):
        """Annotate each record with the total paid so lists avoid one query per row."""
        return self.annotate(
            total_paid=Coalesce(
                Sum("payments__amount"),
                Value(ZERO),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            )
        )


class FeeRecord(models.Model):
    """The hostel fee one student owes for one term (FR-5.1)."""

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="fee_records",
        limit_choices_to={"role": "student"},
    )
    term = models.CharField(max_length=30, help_text="For example, 2026-27 Odd Semester.")
    amount_due = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(MIN_AMOUNT)]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = FeeRecordQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "term"], name="unique_fee_record_per_student_term"
            ),
        ]

    def __str__(self):
        return f"{self.student.srn} - {self.term}"

    @property
    def amount_paid(self):
        if hasattr(self, "total_paid"):
            return self.total_paid
        return self.payments.aggregate(total=Sum("amount"))["total"] or ZERO

    @property
    def balance(self):
        return self.amount_due - self.amount_paid

    @property
    def is_fully_paid(self):
        return self.balance <= ZERO

    def clean(self):
        if self.pk and self.amount_due is not None and self.amount_due < self.amount_paid:
            raise ValidationError(
                {"amount_due": "Amount due cannot be less than the amount already paid."}
            )

    def record_payment(self, *, amount, paid_on, recorded_by):
        """Save a payment while holding a row lock so two admins cannot overpay (FR-5.3)."""
        with transaction.atomic():
            locked = FeeRecord.objects.select_for_update().get(pk=self.pk)
            payment = Payment(
                fee_record=locked, amount=amount, paid_on=paid_on, recorded_by=recorded_by
            )
            payment.full_clean()
            payment.save()
        return payment


class Payment(models.Model):
    """A payment made at the college office and recorded by an Admin (FR-5.2)."""

    fee_record = models.ForeignKey(FeeRecord, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(MIN_AMOUNT)]
    )
    paid_on = models.DateField(default=timezone.localdate)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recorded_payments"
    )
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_on", "-recorded_at"]

    def __str__(self):
        return f"{self.fee_record} - {self.amount}"

    def clean(self):
        errors = {}
        if self.paid_on and self.paid_on > timezone.localdate():
            errors["paid_on"] = "Payment date cannot be in the future."
        if self.amount is not None and self.fee_record_id:
            outstanding = self.fee_record.balance
            if self.pk:
                outstanding += Payment.objects.get(pk=self.pk).amount
            if self.amount > outstanding:
                errors["amount"] = (
                    f"Payment cannot exceed the outstanding balance of ₹{outstanding}."
                )
        if errors:
            raise ValidationError(errors)
