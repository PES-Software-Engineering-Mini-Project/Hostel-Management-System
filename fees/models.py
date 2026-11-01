from decimal import Decimal

from django.conf import settings
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce, Lower
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
    """The hostel fee one student owes for one term (FR-5.1).

    The amount due comes from the student's allotted room when the record is created and is
    then fixed for that term: moving rooms or changing a room's fee later does not rewrite a
    bill that may already be part-paid. The next term's record uses the new room.
    """

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="fee_records",
        limit_choices_to={"role": "student"},
    )
    room = models.ForeignKey(
        "rooms.Room",
        on_delete=models.PROTECT,
        related_name="fee_records",
        null=True,
        blank=True,
        help_text="The room the fee was calculated from. Empty for records made before allocation.",
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
                "student",
                Lower("term"),
                name="unique_fee_record_per_student_term",
                violation_error_message="This student already has a fee record for this term.",
            ),
        ]

    def __str__(self):
        return f"{self.student.srn} - {self.term}"

    @staticmethod
    def term_fee_for(room):
        return room.monthly_fee * settings.HMS_MONTHS_PER_TERM

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

    @property
    def receipt_number(self):
        """The 10-digit numeric receipt number from the SRS data dictionary."""
        return f"{self.pk:010d}"

    @property
    def balance_after(self):
        """Balance left on the fee record right after this payment (FR-5.5).

        Payments are numbered in the order they are recorded, so the earlier ones are those
        with a lower primary key.
        """
        paid_so_far = (
            self.fee_record.payments.filter(pk__lte=self.pk).aggregate(total=Sum("amount"))[
                "total"
            ]
            or ZERO
        )
        return self.fee_record.amount_due - paid_so_far

    def clean(self):
        # fee_record and recorded_by are set by the view, not typed into the payment form, so
        # their errors are non-field errors; a field key would crash a form that omits them.
        errors = {}
        integrity_errors = []
        previous = Payment.objects.filter(pk=self.pk).first() if self.pk else None
        moved = previous is not None and previous.fee_record_id != self.fee_record_id
        if moved:
            integrity_errors.append("A recorded payment cannot be moved to another fee record.")
        if self.recorded_by_id and self.recorded_by.role != self.recorded_by.Role.ADMIN:
            integrity_errors.append("Only an Admin can record a payment.")
        if integrity_errors:
            errors[NON_FIELD_ERRORS] = integrity_errors
        if self.paid_on and self.paid_on > timezone.localdate():
            errors["paid_on"] = "Payment date cannot be in the future."
        if self.amount is not None and self.fee_record_id and not moved:
            outstanding = self.fee_record.balance
            if previous:
                outstanding += previous.amount
            if self.amount > outstanding:
                errors["amount"] = (
                    f"Payment cannot exceed the outstanding balance of ₹{outstanding}."
                )
        if errors:
            raise ValidationError(errors)
