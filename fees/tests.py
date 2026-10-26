from django.apps import apps
from django.test import SimpleTestCase


class FeesAppTests(SimpleTestCase):
    def test_app_is_installed(self):
        self.assertTrue(apps.is_installed("fees"))
