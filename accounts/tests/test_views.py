from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from complaints.models import Complaint
from fees.models import FeeRecord
from rooms.models import Block, Room, RoomApplication

class AuthenticationFlowTests(TestCase):
    def setUp(self):
        self.student = get_user_model().objects.create_user(
            srn="PES1UG23CS010", email="student@example.com", password="student-password",
            first_name="Student", last_name="User", contact_number="9876543210",
        )
        self.admin_user = get_user_model().objects.create_user(
            srn="PES1UG23CS011", email="admin@example.com", password="admin-password",
            first_name="Admin", last_name="User", contact_number="9876543211",
            role=get_user_model().Role.ADMIN,
        )

    def test_login_page_uses_srn_label_and_csrf_protection(self):
        response = self.client.get(reverse("login"))

        self.assertContains(response, "SRN")
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_student_login_redirects_to_student_area(self):
        response = self.client.post(
            reverse("login"),
            {"username": "pes1ug23cs010", "password": "student-password"},
        )

        self.assertRedirects(response, reverse("student-dashboard"))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_admin_login_redirects_to_admin_area(self):
        response = self.client.post(
            reverse("login"),
            {"username": "PES1UG23CS011", "password": "admin-password"},
        )

        self.assertRedirects(response, reverse("admin-dashboard"))

    def test_invalid_login_shows_one_generic_error(self):
        response = self.client.post(
            reverse("login"),
            {"username": "PES1UG23CS010", "password": "wrong-password"},
        )

        self.assertContains(response, "Please enter a valid SRN and password.")
        self.assertNotContains(response, "student-password")

    def test_student_cannot_access_admin_area(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("admin-dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_is_sent_to_login_for_admin_area(self):
        response = self.client.get(reverse("admin-dashboard"))

        self.assertRedirects(response, f"{reverse('login')}?next={reverse('admin-dashboard')}")

    def test_admin_dashboard_shows_live_room_fee_and_complaint_metrics(self):
        block = Block.objects.create(name="A Block", number_of_floors=2)
        Room.objects.create(
            block=block, room_number="101", floor=1, room_type=Room.RoomType.DOUBLE,
            capacity=2, monthly_fee=Decimal("5000.00"), occupied_count=1,
        )
        Room.objects.create(
            block=block, room_number="102", floor=1, room_type=Room.RoomType.SINGLE,
            capacity=1, monthly_fee=Decimal("6000.00"), occupied_count=1,
        )
        second_student = get_user_model().objects.create_user(
            srn="PES1UG23CS012", email="second@example.com", password="student-password",
            first_name="Second", last_name="Student", contact_number="9876543212",
        )
        first_fee = FeeRecord.objects.create(
            student=self.student, term="2026-27 Odd", amount_due=Decimal("100.00")
        )
        first_fee.record_payment(
            amount=Decimal("40.00"), paid_on="2026-10-01", recorded_by=self.admin_user
        )
        second_fee = FeeRecord.objects.create(
            student=self.student, term="2026-27 Even", amount_due=Decimal("30.00")
        )
        second_fee.record_payment(
            amount=Decimal("10.00"), paid_on="2026-10-01", recorded_by=self.admin_user
        )
        paid_fee = FeeRecord.objects.create(
            student=second_student, term="2026-27 Odd", amount_due=Decimal("50.00")
        )
        paid_fee.record_payment(
            amount=Decimal("50.00"), paid_on="2026-10-01", recorded_by=self.admin_user
        )
        Complaint.objects.create(
            student=self.student, category=Complaint.Category.PLUMBING, description="Leaking tap."
        )
        Complaint.objects.create(
            student=second_student, category=Complaint.Category.ELECTRICAL,
            description="Light is not working.", status=Complaint.Status.IN_PROGRESS,
        )
        Complaint.objects.create(
            student=second_student, category=Complaint.Category.CLEANING,
            description="Resolved complaint.", status=Complaint.Status.RESOLVED,
        )
        RoomApplication.objects.create(student=self.student)
        RoomApplication.objects.create(
            student=second_student, status=RoomApplication.Status.ALLOTTED
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_rooms"], 2)
        self.assertEqual(response.context["occupied_rooms"], 2)
        self.assertEqual(response.context["occupancy_percentage"], Decimal("66.7"))
        self.assertEqual(response.context["students_with_dues"], 1)
        self.assertEqual(response.context["total_amount_owed"], Decimal("80.00"))
        self.assertEqual(response.context["active_complaints"], 2)
        self.assertContains(response, "66.7% of beds occupied")
        self.assertContains(response, "₹80.00 outstanding")
        self.assertContains(response, "Open or In Progress")
        self.assertEqual(response.context["pending_applications"], 1)
        self.assertContains(response, reverse("rooms:pending-applications"))

    def test_logout_ends_the_session_and_protected_area_requires_login(self):
        self.client.force_login(self.student)

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("login"))
        protected_response = self.client.get(reverse("student-dashboard"))
        self.assertRedirects(
            protected_response,
            f"{reverse('login')}?next={reverse('student-dashboard')}",
        )


class RegistrationViewTests(TestCase):
    def registration_data(self, **overrides):
        data = {
            "srn": "PES1UG23CS201",
            "first_name": "New",
            "last_name": "Student",
            "email": "new.student@example.com",
            "contact_number": "9876543210",
            "password": "New-Student-Password-932!",
            "confirm_password": "New-Student-Password-932!",
        }
        data.update(overrides)
        return data

    def test_registration_creates_hashed_student_and_redirects_to_login(self):
        response = self.client.post(reverse("register"), self.registration_data(), follow=True)

        self.assertRedirects(response, reverse("login"))
        user = get_user_model().objects.get(srn="PES1UG23CS201")
        self.assertEqual(user.role, get_user_model().Role.STUDENT)
        self.assertTrue(user.check_password("New-Student-Password-932!"))
        self.assertNotEqual(user.password, "New-Student-Password-932!")
        self.assertContains(response, "Registration successful")

    def test_invalid_registration_keeps_typed_values_but_not_passwords(self):
        response = self.client.post(
            reverse("register"),
            self.registration_data(email="not-an-email", password="short", confirm_password="short"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="PES1UG23CS201"')
        self.assertContains(response, 'value="New"')
        self.assertContains(response, 'value="Student"')
        self.assertNotContains(response, 'value="short"')

    def test_new_student_can_log_in_and_reaches_student_dashboard(self):
        self.client.post(reverse("register"), self.registration_data())

        response = self.client.post(
            reverse("login"),
            {"username": "pes1ug23cs201", "password": "New-Student-Password-932!"},
        )

        self.assertRedirects(response, reverse("student-dashboard"))

    def test_logged_in_user_is_redirected_away_from_registration(self):
        user = get_user_model().objects.create_user(
            srn="PES1UG23CS202", email="signedin@example.com", password="password-123",
            first_name="Signed", last_name="In", contact_number="9876543210",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("register"))

        self.assertRedirects(response, reverse("student-dashboard"))
