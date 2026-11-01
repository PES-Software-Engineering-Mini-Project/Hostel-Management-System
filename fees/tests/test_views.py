"""Integration tests: URL -> view -> form -> model -> database, with role checks (FR-5, NFR-3)."""

from decimal import Decimal

from django.conf import settings
from django.shortcuts import resolve_url
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from fees.models import FeeRecord, Payment

from .helpers import allot_room, make_admin, make_fee_record, make_user


class FeeViewTestCase(TestCase):
    def setUp(self):
        self.admin_user = make_admin()
        self.student = make_user("PES1UG23CS501", first_name="Asha")
        self.other_student = make_user("PES1UG23CS502", first_name="Ravi")
        self.record = make_fee_record(self.student, term="2026-27 Odd", amount_due="10000.00")
        self.other_record = make_fee_record(
            self.other_student, term="2026-27 Even", amount_due="12000.00"
        )
        self.today = timezone.localdate().isoformat()

    def payment_url(self, record):
        return reverse("fees:record-payment", args=[record.pk])


class AdminFeeManagementTests(FeeViewTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin_user)

    def test_fee_list_shows_every_student_with_balance(self):
        self.record.record_payment(
            amount=Decimal("2500.00"), paid_on=timezone.localdate(), recorded_by=self.admin_user
        )

        response = self.client.get(reverse("fees:fee-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PES1UG23CS501")
        self.assertContains(response, "PES1UG23CS502")
        self.assertContains(response, "7500.00")

    @override_settings(HMS_MONTHS_PER_TERM=6)
    def test_admin_creates_fee_record_from_the_allotted_room(self):
        room = allot_room(self.student, monthly_fee="9000.00")

        response = self.client.post(
            reverse("fees:fee-create"),
            {"student": self.student.pk, "term": "2027-28 Odd", "amount_due": "1.00"},
            follow=True,
        )

        self.assertRedirects(response, reverse("fees:fee-list"))
        record = FeeRecord.objects.get(student=self.student, term="2027-28 Odd")
        self.assertEqual(record.amount_due, Decimal("54000.00"))
        self.assertEqual(record.room, room)
        self.assertContains(response, "Fee record added for PES1UG23CS501")
        self.assertContains(response, "A Block 101")

    def test_fee_form_has_no_amount_field(self):
        response = self.client.get(reverse("fees:fee-create"))

        self.assertNotContains(response, 'name="amount_due"')

    def test_student_without_room_cannot_be_billed(self):
        response = self.client.post(
            reverse("fees:fee-create"), {"student": self.student.pk, "term": "2027-28 Odd"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose a student who has an allotted room.")
        self.assertFalse(FeeRecord.objects.filter(term="2027-28 Odd").exists())

    def test_duplicate_fee_record_keeps_typed_values_and_shows_field_error(self):
        allot_room(self.student)

        response = self.client.post(
            reverse("fees:fee-create"), {"student": self.student.pk, "term": "2026-27 Odd"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This student already has a fee record for this term.")
        self.assertContains(response, 'value="2026-27 Odd"')
        self.assertEqual(FeeRecord.objects.filter(student=self.student).count(), 1)

    def test_admin_records_payment_and_balance_updates(self):
        response = self.client.post(
            self.payment_url(self.record), {"amount": "4000.00", "paid_on": self.today}, follow=True
        )

        payment = Payment.objects.get(fee_record=self.record)
        self.assertRedirects(response, reverse("fees:receipt", args=[payment.pk]))
        self.assertEqual(payment.amount, Decimal("4000.00"))
        self.assertEqual(payment.recorded_by, self.admin_user)
        self.assertEqual(self.record.balance, Decimal("6000.00"))
        self.assertContains(response, "Payment of ₹4000.00 recorded for PES1UG23CS501")

    def test_overpayment_is_rejected_without_saving(self):
        response = self.client.post(
            self.payment_url(self.record), {"amount": "10000.01", "paid_on": self.today}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Payment cannot exceed the outstanding balance")
        self.assertFalse(Payment.objects.exists())

    def test_fully_paid_record_hides_payment_form(self):
        self.record.record_payment(
            amount=Decimal("10000.00"), paid_on=timezone.localdate(), recorded_by=self.admin_user
        )

        response = self.client.get(self.payment_url(self.record))

        self.assertContains(response, "This fee has been paid in full.")
        self.assertNotContains(response, 'name="amount"')

    def test_unknown_fee_record_returns_404(self):
        response = self.client.get(reverse("fees:record-payment", args=[99999]))

        self.assertEqual(response.status_code, 404)

    def test_admin_cannot_open_student_fee_page(self):
        response = self.client.get(reverse("fees:my-fees"))

        self.assertEqual(response.status_code, 403)


class StudentFeeAccessTests(FeeViewTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.student)

    def test_student_sees_only_their_own_fees(self):
        response = self.client.get(reverse("fees:my-fees"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2026-27 Odd")
        self.assertContains(response, "10000.00")
        self.assertNotContains(response, "2026-27 Even")
        self.assertNotContains(response, "12000.00")

    def test_student_sees_their_payment_history(self):
        self.record.record_payment(
            amount=Decimal("3210.00"), paid_on=timezone.localdate(), recorded_by=self.admin_user
        )

        response = self.client.get(reverse("fees:my-fees"))

        self.assertContains(response, "3210.00")
        self.assertContains(response, "6790.00 due")

    def test_student_cannot_open_admin_fee_pages(self):
        for url in (
            reverse("fees:fee-list"),
            reverse("fees:fee-create"),
            self.payment_url(self.record),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_student_cannot_record_payment_by_posting_to_admin_url(self):
        response = self.client.post(
            self.payment_url(self.other_record), {"amount": "100.00", "paid_on": self.today}
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Payment.objects.exists())

    def test_student_cannot_create_fee_record(self):
        response = self.client.post(
            reverse("fees:fee-create"),
            {"student": self.student.pk, "term": "Fake", "amount_due": "1.00"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(FeeRecord.objects.filter(term="Fake").exists())


class AnonymousFeeAccessTests(FeeViewTestCase):
    def test_logged_out_users_are_sent_to_login(self):
        for url in (reverse("fees:my-fees"), reverse("fees:fee-list")):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(
                    response,
                    f"{resolve_url(settings.LOGIN_URL)}?next={url}",
                    fetch_redirect_response=False,
                )


class DashboardLinkTests(FeeViewTestCase):
    def test_student_dashboard_links_to_my_fees(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("student-dashboard"))

        self.assertContains(response, reverse("fees:my-fees"))

    def test_admin_dashboard_links_to_fee_management(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin-dashboard"))

        self.assertContains(response, reverse("fees:fee-list"))


class ReceiptTests(FeeViewTestCase):
    """FR-5.5 and FR-5.6: one receipt per payment; students see only their own (NFR-3)."""

    def setUp(self):
        super().setUp()
        self.room = allot_room(self.student, room_number="204")
        self.record.room = self.room
        self.record.save()
        self.payment = self.record.record_payment(
            amount=Decimal("2500.00"), paid_on=timezone.localdate(), recorded_by=self.admin_user
        )
        self.other_payment = self.other_record.record_payment(
            amount=Decimal("100.00"), paid_on=timezone.localdate(), recorded_by=self.admin_user
        )

    def receipt_url(self, payment, download=False):
        name = "fees:receipt-download" if download else "fees:receipt"
        return reverse(name, args=[payment.pk])

    def test_receipt_shows_every_field_from_the_srs(self):
        self.client.force_login(self.student)

        response = self.client.get(self.receipt_url(self.payment))

        self.assertEqual(response.status_code, 200)
        for text in (
            self.payment.receipt_number,
            "Asha",
            "PES1UG23CS501",
            "A Block, room 204",
            "2500.00",
            "7500.00",
            timezone.localdate().strftime("%Y"),
        ):
            self.assertContains(response, text)

    def test_student_can_download_their_own_receipt(self):
        self.client.force_login(self.student)

        response = self.client.get(self.receipt_url(self.payment, download=True))

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn(self.payment.receipt_number, response["Content-Disposition"])
        self.assertContains(response, "PES1UG23CS501")

    def test_student_cannot_open_another_students_receipt(self):
        self.client.force_login(self.student)

        for download in (False, True):
            with self.subTest(download=download):
                response = self.client.get(self.receipt_url(self.other_payment, download))
                self.assertEqual(response.status_code, 404)

    def test_admin_can_open_any_receipt(self):
        self.client.force_login(self.admin_user)

        for payment in (self.payment, self.other_payment):
            with self.subTest(payment=payment.pk):
                self.assertEqual(self.client.get(self.receipt_url(payment)).status_code, 200)
                self.assertEqual(
                    self.client.get(self.receipt_url(payment, download=True)).status_code, 200
                )

    def test_logged_out_user_is_sent_to_login(self):
        url = self.receipt_url(self.payment)

        response = self.client.get(url)

        self.assertRedirects(
            response, f"{resolve_url(settings.LOGIN_URL)}?next={url}", fetch_redirect_response=False
        )

    def test_receipt_links_from_my_fees_and_payment_history(self):
        self.client.force_login(self.student)
        self.assertContains(self.client.get(reverse("fees:my-fees")), self.receipt_url(self.payment))

        self.client.force_login(self.admin_user)
        self.assertContains(
            self.client.get(self.payment_url(self.record)), self.receipt_url(self.payment)
        )
