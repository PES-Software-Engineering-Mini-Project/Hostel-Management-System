"""NFR-1 usability: consistent role navigation and forms that keep typed values."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from fees.models import FeeRecord


class UsabilityTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.student = User.objects.create_user(
            srn="PES1UG23CS010", email="student@example.com", password="student-password",
            first_name="Student", last_name="User", contact_number="9876543210",
        )
        self.admin_user = User.objects.create_user(
            srn="PES1UG23CS012", email="admin@example.com", password="admin-password",
            first_name="Admin", last_name="User", contact_number="9876543212",
            role=User.Role.ADMIN,
        )


class RoleNavigationTests(UsabilityTestCase):
    student_pages = ["student-dashboard", "fees:my-fees", "complaints:my-complaints", "complaints:raise"]

    def test_student_nav_consistent_on_every_page_with_logout(self):
        self.client.force_login(self.student)
        for name in self.student_pages:
            response = self.client.get(reverse(name))
            self.assertContains(response, reverse("student-dashboard"), msg_prefix=f"{name}: ")
            self.assertContains(response, reverse("fees:my-fees"), msg_prefix=f"{name}: ")
            self.assertContains(response, reverse("complaints:raise"), msg_prefix=f"{name}: ")
            self.assertContains(response, "Log out", msg_prefix=f"{name}: ")
            self.assertNotContains(response, reverse("fees:fee-list"), msg_prefix=f"{name}: ")

    def test_admin_nav_consistent_on_every_page_with_logout(self):
        self.client.force_login(self.admin_user)
        for name in ["admin-dashboard", "fees:fee-list", "complaints:complaint-list"]:
            response = self.client.get(reverse(name))
            self.assertContains(response, reverse("admin-dashboard"), msg_prefix=f"{name}: ")
            self.assertContains(response, reverse("fees:fee-list"), msg_prefix=f"{name}: ")
            self.assertContains(response, reverse("complaints:complaint-list"), msg_prefix=f"{name}: ")
            self.assertContains(response, "Log out", msg_prefix=f"{name}: ")

    def test_core_actions_within_two_clicks_of_dashboard(self):
        self.client.force_login(self.student)
        dashboard = self.client.get(reverse("student-dashboard"))
        self.assertContains(dashboard, reverse("complaints:raise"))  # 1 click

        FeeRecord.objects.create(
            student=self.student, term="2026-27 Odd Semester", amount_due="20000.00"
        )
        self.client.force_login(self.admin_user)
        dashboard = self.client.get(reverse("admin-dashboard"))
        self.assertContains(dashboard, reverse("fees:fee-list"))  # click 1
        fee_list = self.client.get(reverse("fees:fee-list"))
        self.assertContains(fee_list, "Record payment")  # click 2


class FormUsabilityTests(UsabilityTestCase):
    def test_complaint_form_error_keeps_typed_description(self):
        self.client.force_login(self.student)

        response = self.client.post(
            reverse("complaints:raise"),
            {"category": "", "description": "The corridor light is flickering."},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")
        self.assertContains(response, "The corridor light is flickering.")

    def test_fee_form_error_keeps_typed_values(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("fees:fee-create"),
            {"student": "", "term": "2026-27 Odd Semester", "amount_due": "abc"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="2026-27 Odd Semester"')
