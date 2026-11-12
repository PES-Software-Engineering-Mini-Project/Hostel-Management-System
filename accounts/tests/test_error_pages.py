"""NFR-8 (issue #27): plain error pages, never a stack trace when DEBUG is false."""

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.views import defaults


def make_user(srn, **extra):
    return get_user_model().objects.create_user(
        srn=srn,
        email=f"{srn.lower()}@example.com",
        password="test-password-123",
        first_name="Test",
        last_name=srn,
        contact_number="9876543210",
        **extra,
    )


class ErrorPageTests(TestCase):
    """The test runner always runs with DEBUG false, which is the deployment setting
    these pages exist for. Each check also asserts no technical detail leaks."""

    def setUp(self):
        self.student = make_user("PES1UG23CS721")

    def test_404_uses_the_plain_page(self):
        client = Client()
        client.force_login(self.student)

        response = client.get("/no-such-page/")

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Page not found", status_code=404)
        self.assertNotContains(response, "Traceback", status_code=404)
        self.assertNotContains(response, "Django", status_code=404)

    def test_404_for_another_students_record_uses_the_plain_page(self):
        client = Client()
        client.force_login(self.student)

        response = client.get(reverse("complaints:detail", args=[99999]))

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertNotContains(response, "Traceback", status_code=404)

    def test_403_uses_the_plain_page(self):
        client = Client()
        client.force_login(self.student)

        response = client.get(reverse("complaints:complaint-list"))  # admin-only page

        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "403.html")
        self.assertContains(response, "Access denied", status_code=403)
        self.assertNotContains(response, "Traceback", status_code=403)
        self.assertNotContains(response, "PermissionDenied", status_code=403)

    def test_500_uses_the_plain_page_without_any_request_context(self):
        # Django's default handler500 renders 500.html with no context at all, so the
        # template must not depend on the request or the logged-in user.
        request = RequestFactory().get("/")

        response = defaults.server_error(request)

        self.assertEqual(response.status_code, 500)
        content = response.content.decode()
        self.assertIn("Something went wrong", content)
        self.assertNotIn("Traceback", content)
        self.assertNotIn("Exception", content)
