"""NFR-3 security suite: role checks, ID tampering, CSRF and password storage.

Covers every admin URL and per-student URL on main. Fees, complaints and
visitors have no student-facing URL that takes another user's id, so
tampering tests assert record isolation instead.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from complaints.models import Complaint
from fees.models import FeeRecord


class SecurityTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.student = User.objects.create_user(
            srn="PES1UG23CS010", email="student@example.com", password="student-password",
            first_name="Student", last_name="User", contact_number="9876543210",
        )
        self.other_student = User.objects.create_user(
            srn="PES1UG23CS011", email="other@example.com", password="other-password",
            first_name="Other", last_name="Student", contact_number="9876543211",
        )
        self.admin_user = User.objects.create_user(
            srn="PES1UG23CS012", email="admin@example.com", password="admin-password",
            first_name="Admin", last_name="User", contact_number="9876543212",
            role=User.Role.ADMIN,
        )
        self.fee_record = FeeRecord.objects.create(
            student=self.student, term="2026-27 Odd Semester", amount_due="1000.00"
        )
        self.complaint = Complaint.objects.create(
            student=self.student, category="plumbing", description="Bathroom tap leaks."
        )

    def admin_urls(self):
        return [
            reverse("admin-dashboard"),
            reverse("fees:fee-list"),
            reverse("fees:fee-create"),
            reverse("fees:record-payment", args=[self.fee_record.pk]),
            reverse("complaints:complaint-list"),
            reverse("complaints:update-status", args=[self.complaint.pk]),
            reverse("student-list"),
            reverse("student-edit", args=[self.student.pk]),
        ]


class PasswordStorageTests(SecurityTestCase):
    def test_passwords_are_hashed_never_plain_text(self):
        for user, raw in [
            (self.student, "student-password"),
            (self.admin_user, "admin-password"),
        ]:
            self.assertNotEqual(user.password, raw)
            self.assertTrue(user.password.startswith(("pbkdf2_", "argon2", "bcrypt")))
            self.assertTrue(user.check_password(raw))

    def test_registration_rejects_weak_password(self):
        response = self.client.post(reverse("register"), {
            "srn": "PES1UG23CS201", "first_name": "Weak", "last_name": "Pass",
            "email": "weak@example.com", "contact_number": "9876543299",
            "password": "password", "confirm_password": "password",
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            get_user_model().objects.filter(srn="PES1UG23CS201").exists()
        )


class AdminUrlRoleTests(SecurityTestCase):
    def test_student_gets_403_on_every_admin_url(self):
        self.client.force_login(self.student)
        for url in self.admin_urls():
            for method in (self.client.get, self.client.post):
                response = method(url)
                self.assertEqual(
                    response.status_code, 403, f"{method.__name__.upper()} {url}"
                )

    def test_anonymous_user_is_redirected_to_login_on_every_admin_url(self):
        for url in self.admin_urls():
            response = self.client.get(url)
            self.assertRedirects(
                response, f"{reverse('login')}?next={url}", msg_prefix=f"GET {url}: "
            )


class IdTamperingTests(SecurityTestCase):
    def test_student_cannot_open_another_students_complaint_by_changing_url(self):
        self.client.force_login(self.other_student)

        response = self.client.get(reverse("complaints:detail", args=[self.complaint.pk]))

        self.assertEqual(response.status_code, 404)

    def test_my_fees_shows_only_the_signed_in_students_records(self):
        FeeRecord.objects.create(
            student=self.other_student, term="2026-27 Odd Semester", amount_due="500.00"
        )
        self.client.force_login(self.student)

        response = self.client.get(reverse("fees:my-fees"))

        self.assertContains(response, "1000.00")
        self.assertNotContains(response, "500.00")

    def test_my_complaints_shows_only_the_signed_in_students_complaints(self):
        Complaint.objects.create(
            student=self.other_student, category="electrical", description="Fan stopped."
        )
        self.client.force_login(self.student)

        response = self.client.get(reverse("complaints:my-complaints"))

        self.assertContains(response, "Bathroom tap leaks.")
        self.assertNotContains(response, "Fan stopped.")

    def test_fee_and_complaint_owner_never_come_from_posted_data(self):
        self.client.force_login(self.other_student)
        self.client.post(
            reverse("complaints:raise"),
            {"category": "other", "description": "Tries to set owner.",
             "student": self.student.pk},
        )

        spoofed = Complaint.objects.get(description="Tries to set owner.")
        self.assertEqual(spoofed.student, self.other_student)


class CsrfTests(SecurityTestCase):
    def test_every_data_changing_form_page_ships_a_csrf_token(self):
        form_pages = [
            (None, reverse("login")),
            (None, reverse("register")),
            (self.student, reverse("complaints:raise")),
            (self.student, reverse("complaints:detail", args=[self.complaint.pk])),
            (self.student, reverse("fees:my-fees")),
            (self.admin_user, reverse("fees:fee-create")),
            (self.admin_user, reverse("fees:record-payment", args=[self.fee_record.pk])),
            (self.admin_user, reverse("complaints:complaint-list")),
        ]
        for user, url in form_pages:
            if user:
                self.client.force_login(user)
            else:
                self.client.logout()
            response = self.client.get(url)
            self.assertContains(response, "csrfmiddlewaretoken", msg_prefix=f"GET {url}: ")

    @override_settings(CSRF_COOKIE_SECURE=False)
    def test_post_without_csrf_token_is_rejected(self):
        csrf_client = self.client_class(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin_user)

        response = csrf_client.post(
            reverse("complaints:update-status", args=[self.complaint.pk]),
            {"status": "in_progress"},
        )

        self.assertEqual(response.status_code, 403)
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, "open")

    def test_status_change_is_post_only(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse("complaints:update-status", args=[self.complaint.pk])
        )

        self.assertEqual(response.status_code, 405)
