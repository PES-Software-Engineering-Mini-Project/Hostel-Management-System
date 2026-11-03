"""NFR-8 availability: a crash or a refused page shows a plain page, never a stack trace.

SAD 4.4: an unhandled error is written to the application log (django.request).
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.test.utils import override_settings
from django.urls import path

SECRET = "secret-internal-detail-xyz"


def boom(request):
    raise RuntimeError(SECRET)


urlpatterns = [path("boom/", boom)]


@override_settings(DEBUG=False)
class ErrorPageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.student = User.objects.create_user(
            srn="PES1UG23CS020", email="s@example.com", password="pw-12345-x",
            first_name="S", last_name="T", contact_number="9876543210",
        )

    def assert_plain(self, response, status, template):
        self.assertEqual(response.status_code, status)
        self.assertTemplateUsed(response, template)
        body = response.content.decode()
        for leak in ("Traceback", "Exception", "RuntimeError", SECRET, "/home/", ".py"):
            self.assertNotIn(leak, body)
        self.assertIn('href="/"', body)  # link back home

    def test_403_for_student_on_admin_page(self):
        self.client.force_login(self.student)
        response = self.client.get("/rooms/")
        self.assert_plain(response, 403, "403.html")
        self.assertNotIn("You do not have permission to access this area.", response.content.decode())

    def test_404_for_unknown_url(self):
        self.client.force_login(self.student)
        self.assert_plain(self.client.get("/no-such-page/"), 404, "404.html")

    def test_404_for_logged_out_user_needs_no_session(self):
        self.assert_plain(self.client.get("/no-such-page/"), 404, "404.html")

    @override_settings(ROOT_URLCONF=__name__)
    def test_500_page_and_log(self):
        client = Client(raise_request_exception=False)
        with self.assertLogs("django.request", level="ERROR") as logs:
            response = client.get("/boom/")
        self.assert_plain(response, 500, "500.html")
        self.assertIn("Internal Server Error", logs.output[0])  # SAD 4.4: logged
        self.assertIn(SECRET, "\n".join(logs.output))  # detail goes to the log, not the page

    def test_500_renders_without_request_context(self):
        from django.template.loader import render_to_string

        html = render_to_string("500.html")
        self.assertIn('href="/"', html)
        self.assertNotIn("Traceback", html)
