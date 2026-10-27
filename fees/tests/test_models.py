"""Unit tests for fee records, payments and fee forms (FR-5.1 to FR-5.3)."""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from fees.forms import FeeRecordForm, PaymentForm
from fees.models import FeeRecord, Payment

from .helpers import make_admin, make_fee_record, make_user


class FeeRecordModelTests(TestCase):
    def setUp(self):
        self.student = make_user("PES1UG23CS101")
        self.admin_user = make_admin()

    def test_new_record_has_full_balance_and_nothing_paid(self):
        record = make_fee_record(self.student, amount_due="50000.00")

        self.assertEqual(record.amount_paid, Decimal("0.00"))
        self.assertEqual(record.balance, Decimal("50000.00"))
        self.assertFalse(record.is_fully_paid)

    def test_balance_subtracts_all_payments(self):
        record = make_fee_record(self.student, amount_due="50000.00")
        today = timezone.localdate()
        record.record_payment(amount=Decimal("20000.00"), paid_on=today, recorded_by=self.admin_user)
        record.record_payment(amount=Decimal("5000.50"), paid_on=today, recorded_by=self.admin_user)

        self.assertEqual(record.amount_paid, Decimal("25000.50"))
        self.assertEqual(record.balance, Decimal("24999.50"))

    def test_with_totals_annotation_matches_property(self):
        record = make_fee_record(self.student)
        record.record_payment(
            amount=Decimal("1000.00"), paid_on=timezone.localdate(), recorded_by=self.admin_user
        )

        annotated = FeeRecord.objects.with_totals().get(pk=record.pk)

        self.assertEqual(annotated.total_paid, Decimal("1000.00"))
        self.assertEqual(annotated.balance, Decimal("49000.00"))

    def test_one_record_per_student_per_term(self):
        make_fee_record(self.student, term="2026-27 Odd")

        with transaction.atomic(), self.assertRaises(IntegrityError):
            make_fee_record(self.student, term="2026-27 Odd")

    def test_case_variant_term_is_a_duplicate_in_the_database(self):
        make_fee_record(self.student, term="2026-27 Odd")

        with transaction.atomic(), self.assertRaises(IntegrityError):
            make_fee_record(self.student, term="2026-27 ODD")

    def test_case_variant_term_fails_model_validation(self):
        make_fee_record(self.student, term="2026-27 Odd")
        record = FeeRecord(student=self.student, term="2026-27 odd", amount_due=Decimal("100.00"))

        with self.assertRaises(ValidationError) as caught:
            record.full_clean()
        self.assertIn(
            "This student already has a fee record for this term.",
            caught.exception.messages,
        )

    def test_same_term_allowed_for_different_students(self):
        other = make_user("PES1UG23CS102")
        make_fee_record(self.student, term="2026-27 Odd")

        make_fee_record(other, term="2026-27 Odd")

        self.assertEqual(FeeRecord.objects.filter(term="2026-27 Odd").count(), 2)

    def test_amount_due_must_be_positive(self):
        for amount in ("0.00", "-1.00"):
            record = FeeRecord(student=self.student, term="2026-27 Even", amount_due=Decimal(amount))
            with self.subTest(amount=amount), self.assertRaises(ValidationError) as caught:
                record.full_clean()
            self.assertIn("amount_due", caught.exception.message_dict)

    def test_amount_due_cannot_drop_below_amount_paid(self):
        record = make_fee_record(self.student, amount_due="10000.00")
        record.record_payment(
            amount=Decimal("8000.00"), paid_on=timezone.localdate(), recorded_by=self.admin_user
        )

        record.amount_due = Decimal("7999.99")

        with self.assertRaises(ValidationError) as caught:
            record.full_clean()
        self.assertIn("amount_due", caught.exception.message_dict)


class RecordPaymentTests(TestCase):
    def setUp(self):
        self.student = make_user("PES1UG23CS201")
        self.admin_user = make_admin()
        self.record = make_fee_record(self.student, amount_due="10000.00")
        self.today = timezone.localdate()

    def pay(self, amount, paid_on=None):
        return self.record.record_payment(
            amount=Decimal(amount), paid_on=paid_on or self.today, recorded_by=self.admin_user
        )

    def test_partial_payment_is_saved(self):
        payment = self.pay("4000.00")

        self.assertEqual(payment.fee_record, self.record)
        self.assertEqual(payment.recorded_by, self.admin_user)
        self.assertEqual(self.record.balance, Decimal("6000.00"))

    def test_payment_equal_to_balance_clears_the_fee(self):
        self.pay("10000.00")

        self.assertEqual(self.record.balance, Decimal("0.00"))
        self.assertTrue(self.record.is_fully_paid)

    def test_payment_one_paisa_over_balance_is_rejected(self):
        with self.assertRaises(ValidationError) as caught:
            self.pay("10000.01")

        self.assertIn("amount", caught.exception.message_dict)
        self.assertFalse(Payment.objects.exists())

    def test_overpayment_counts_earlier_payments(self):
        self.pay("7000.00")

        with self.assertRaises(ValidationError):
            self.pay("3000.01")
        self.pay("3000.00")

        self.assertTrue(self.record.is_fully_paid)

    def test_any_payment_on_fully_paid_fee_is_rejected(self):
        self.pay("10000.00")

        with self.assertRaises(ValidationError):
            self.pay("0.01")

    def test_zero_and_negative_payments_are_rejected(self):
        for amount in ("0.00", "-500.00"):
            with self.subTest(amount=amount), self.assertRaises(ValidationError) as caught:
                self.pay(amount)
            self.assertIn("amount", caught.exception.message_dict)
        self.assertFalse(Payment.objects.exists())

    def test_future_payment_date_is_rejected(self):
        with self.assertRaises(ValidationError) as caught:
            self.pay("100.00", paid_on=self.today + timedelta(days=1))

        self.assertIn("paid_on", caught.exception.message_dict)

    def test_editing_a_payment_does_not_count_itself_twice(self):
        payment = self.pay("10000.00")

        payment.amount = Decimal("9000.00")
        payment.full_clean()

    def test_payment_cannot_be_moved_to_another_fee_record(self):
        # Moving a fully used 10000 payment onto a fully paid 5000 record must not be allowed;
        # counting the old amount against the new record would hide a 10000 overpayment.
        payment = self.pay("10000.00")
        other = make_fee_record(make_user("PES1UG23CS202"), amount_due="5000.00")
        other.record_payment(
            amount=Decimal("5000.00"), paid_on=self.today, recorded_by=self.admin_user
        )

        payment.fee_record = other

        with self.assertRaises(ValidationError) as caught:
            payment.full_clean()
        self.assertIn(
            "A recorded payment cannot be moved to another fee record.",
            caught.exception.message_dict["__all__"],
        )
        self.assertNotIn("amount", caught.exception.message_dict)

    def test_only_an_admin_can_record_a_payment(self):
        with self.assertRaises(ValidationError) as caught:
            self.record.record_payment(
                amount=Decimal("100.00"), paid_on=self.today, recorded_by=self.student
            )

        self.assertIn(
            "Only an Admin can record a payment.", caught.exception.message_dict["__all__"]
        )
        self.assertFalse(Payment.objects.exists())


class FeeRecordFormTests(TestCase):
    def setUp(self):
        self.student = make_user("PES1UG23CS301")

    def test_valid_form_normalises_term_whitespace(self):
        form = FeeRecordForm(
            data={"student": self.student.pk, "term": "  2026-27   Odd ", "amount_due": "45000"}
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["term"], "2026-27 Odd")

    def test_duplicate_term_error_is_on_the_term_field(self):
        make_fee_record(self.student, term="2026-27 Odd")

        form = FeeRecordForm(
            data={"student": self.student.pk, "term": "2026-27 ODD", "amount_due": "45000"}
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["term"], ["This student already has a fee record for this term."]
        )
        self.assertNotIn("__all__", form.errors)

    def test_admin_users_are_not_offered_as_students(self):
        admin_user = make_admin()

        form = FeeRecordForm()

        self.assertIn(self.student, form.fields["student"].queryset)
        self.assertNotIn(admin_user, form.fields["student"].queryset)


class PaymentFormTests(TestCase):
    def setUp(self):
        self.admin_user = make_admin()
        self.record = make_fee_record(make_user("PES1UG23CS401"), amount_due="5000.00")

    def form(self, amount, paid_on=None):
        return PaymentForm(
            data={"amount": amount, "paid_on": (paid_on or timezone.localdate()).isoformat()},
            fee_record=self.record,
            recorded_by=self.admin_user,
        )

    def test_amount_within_balance_is_valid(self):
        self.assertTrue(self.form("5000.00").is_valid())

    def test_amount_over_balance_shows_error_on_amount_field(self):
        form = self.form("5000.01")

        self.assertFalse(form.is_valid())
        self.assertIn("outstanding balance", form.errors["amount"][0])

    def test_non_numeric_amount_is_rejected(self):
        form = self.form("five thousand")

        self.assertFalse(form.is_valid())
        self.assertIn("amount", form.errors)

    def test_non_admin_recorder_is_a_form_error_not_a_crash(self):
        form = PaymentForm(
            data={"amount": "100.00", "paid_on": timezone.localdate().isoformat()},
            fee_record=self.record,
            recorded_by=self.record.student,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Only an Admin can record a payment.", form.non_field_errors())
