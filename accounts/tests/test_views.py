from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


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
