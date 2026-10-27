from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.forms import StudentRegistrationForm


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


class StudentRegistrationFormTests(TestCase):
    def form_data(self, **overrides):
        data = {
            "srn": "PES1UG23CS101",
            "first_name": "Asha",
            "last_name": "Student",
            "email": "asha@example.com",
            "contact_number": "9876543210",
            "password": "Asha-Strong-Password-932!",
            "confirm_password": "Asha-Strong-Password-932!",
        }
        data.update(overrides)
        return data

    def test_valid_form_creates_a_student_only(self):
        form = StudentRegistrationForm(data=self.form_data())

        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.role, get_user_model().Role.STUDENT)
        self.assertTrue(user.check_password("Asha-Strong-Password-932!"))

    def test_duplicate_srn_is_rejected_case_insensitively(self):
        get_user_model().objects.create_user(
            srn="PES1UG23CS101", email="existing@example.com", password="password-123",
            first_name="Existing", last_name="Student", contact_number="9876543210",
        )

        form = StudentRegistrationForm(data=self.form_data(srn="pes1ug23cs101"))

        self.assertFalse(form.is_valid())
        self.assertIn("srn", form.errors)

    def test_duplicate_email_is_rejected_case_insensitively(self):
        get_user_model().objects.create_user(
            srn="PES1UG23CS102", email="existing@example.com", password="password-123",
            first_name="Existing", last_name="Student", contact_number="9876543210",
        )

        form = StudentRegistrationForm(data=self.form_data(email="EXISTING@EXAMPLE.COM"))

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_password_mismatch_is_rejected(self):
        form = StudentRegistrationForm(data=self.form_data(confirm_password="Different-password-932!"))

        self.assertFalse(form.is_valid())
        self.assertIn("confirm_password", form.errors)

    def test_weak_and_numeric_only_passwords_are_rejected(self):
        for password in ("password", "1234567890"):
            with self.subTest(password=password):
                form = StudentRegistrationForm(data=self.form_data(password=password, confirm_password=password))
                self.assertFalse(form.is_valid())
                self.assertIn("password", form.errors)
