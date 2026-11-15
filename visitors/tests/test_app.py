from django.apps import apps
from django.test import SimpleTestCase


class VisitorsAppTests(SimpleTestCase):
    def test_app_is_installed(self):
        self.assertTrue(apps.is_installed("visitors"))
