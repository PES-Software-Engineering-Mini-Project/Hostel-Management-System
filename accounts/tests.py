from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase


class UserModelTests(TestCase):
    def test_foundation_home_route_uses_the_base_template(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")

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
