"""User manager rules and the already-logged-in redirect (FR-1.3, FR-2.1).

These cover the error paths of ``create_user``/``create_superuser``, which are only
reached from the command line (``createsuperuser``), so the page tests never hit them.
"""
from django.test import TestCase
from django.urls import reverse

from accounts.models import User


class UserManagerTests(TestCase):
    def test_create_user_requires_an_srn(self):
        with self.assertRaisesMessage(ValueError, "The SRN must be set"):
            User.objects.create_user(srn="", email="a@example.com", password="Pass12345!")

    def test_create_user_requires_an_email(self):
        with self.assertRaisesMessage(ValueError, "The email address must be set"):
            User.objects.create_user(srn="PES2UG24CS901", email="", password="Pass12345!")

    def test_create_user_requires_a_password(self):
        with self.assertRaisesMessage(ValueError, "The password must be set"):
            User.objects.create_user(srn="PES2UG24CS902", email="b@example.com", password=None)

    def test_create_superuser_is_a_staff_admin(self):
        user = User.objects.create_superuser(
            srn="pes2ug24cs903", email="c@example.com", password="Pass12345!"
        )
        self.assertEqual(user.srn, "PES2UG24CS903")
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_create_superuser_rejects_missing_staff_flag(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                srn="PES2UG24CS904", email="d@example.com", password="Pass12345!", is_staff=False
            )
        self.assertFalse(User.objects.filter(srn="PES2UG24CS904").exists())


class LoggedInRegisterRedirectTests(TestCase):
    def test_logged_in_admin_opening_register_goes_to_admin_dashboard(self):
        admin = User.objects.create_user(
            srn="PES2UG24CS905", email="e@example.com", password="Pass12345!",
            role=User.Role.ADMIN, is_staff=True,
        )
        self.client.force_login(admin)
        response = self.client.get(reverse("register"))
        self.assertRedirects(response, reverse("admin-dashboard"))
