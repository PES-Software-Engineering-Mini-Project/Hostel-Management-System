from django.apps import apps
from django.test import SimpleTestCase


class RoomsAppTests(SimpleTestCase):
    def test_app_is_installed(self):
        self.assertTrue(apps.is_installed("rooms"))
