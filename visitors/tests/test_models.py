"""Unit tests for the Visitor model rules (FR-7.3)."""

from django.core.exceptions import ValidationError
from django.test import TestCase

from visitors.models import Visitor

from .helpers import allot_room, make_user


class VisitorModelTests(TestCase):
    def setUp(self):
        self.student = make_user("PES1UG23CS801")
        allot_room(self.student)
        self.visitor = Visitor.objects.create(
            name="Ramesh", contact_number="9812345678", purpose="Family visit",
            host=self.student,
        )

    def test_new_visitor_is_inside_with_server_entry_time(self):
        self.assertTrue(self.visitor.is_inside)
        self.assertIsNone(self.visitor.exit_time)
        self.assertIsNotNone(self.visitor.entry_time)

    def test_check_out_records_the_server_exit_time(self):
        self.visitor.check_out()

        self.assertFalse(self.visitor.is_inside)
        self.assertIsNotNone(self.visitor.exit_time)
        self.assertGreaterEqual(self.visitor.exit_time, self.visitor.entry_time)

    def test_checking_out_twice_raises(self):
        self.visitor.check_out()
        first_exit = self.visitor.exit_time

        with self.assertRaises(ValidationError):
            self.visitor.check_out()

        self.visitor.refresh_from_db()
        self.assertEqual(self.visitor.exit_time, first_exit)

    def test_str_shows_name_and_host(self):
        self.assertEqual(str(self.visitor), "Ramesh (host PES1UG23CS801)")
