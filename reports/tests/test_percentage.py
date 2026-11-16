"""Occupancy percentage edge case (SRS §3.1 reports, FR-8.1)."""
from decimal import Decimal

from django.test import SimpleTestCase

from reports.reports import _percentage


class PercentageTests(SimpleTestCase):
    def test_zero_rooms_gives_zero_percent_not_an_error(self):
        self.assertEqual(_percentage(5, 0), Decimal("0.0"))

    def test_normal_percentage_is_rounded_to_one_place(self):
        self.assertEqual(_percentage(1, 3), Decimal("33.3"))
