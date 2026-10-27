from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse


class UserModelTests(TestCase):
    def test_home_route_redirects_to_login(self):
        response = self.client.get("/")

        self.assertRedirects(response, reverse("login"))

    def test_srn_is_login_identifier_and_password_is_hashed(self):
        user = get_user_model().objects.create_user(
            srn="pes1ug23cs001",
            email="student@example.com",
            password="strong-password-123",
            first_name="Test",
            last_name="Student",
            contact_number="9876543210",
        )

        self.assertEqual(get_user_model().USERNAME_FIELD, "srn")
        self.assertEqual(user.srn, "PES1UG23CS001")
        self.assertTrue(user.check_password("strong-password-123"))
        self.assertNotEqual(user.password, "strong-password-123")
        self.assertEqual(user.role, get_user_model().Role.STUDENT)

    def test_srn_and_email_must_be_unique(self):
        user_model = get_user_model()
        user_model.objects.create_user(
            srn="PES1UG23CS002", email="unique@example.com", password="password-123",
            first_name="First", last_name="User", contact_number="9876543210",
        )

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                user_model.objects.create_user(
                    srn="PES1UG23CS002", email="other@example.com", password="password-123",
                    first_name="Second", last_name="User", contact_number="9876543211",
                )

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                user_model.objects.create_user(
                    srn="PES1UG23CS003", email="unique@example.com", password="password-123",
                    first_name="Third", last_name="User", contact_number="9876543212",
                )


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

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('admin-dashboard')}",
        )

    def test_logout_ends_the_session_and_protected_area_requires_login(self):
        self.client.force_login(self.student)

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("login"))
        protected_response = self.client.get(reverse("student-dashboard"))
        self.assertRedirects(
            protected_response,
            f"{reverse('login')}?next={reverse('student-dashboard')}",
        )
