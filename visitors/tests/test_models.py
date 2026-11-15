"""Unit tests for the Visitor model (FR-7.1 to FR-7.5), without the test client."""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from visitors.forms import VisitorForm
from visitors.models import Visitor

from .helpers import give_room, make_user, make_visitor


class VisitorModelTests(TestCase):
    def setUp(self):
        self.student = make_user("PES1UG23CS901")
        give_room(self.student)

    def test_entry_time_is_set_by_the_server_and_exit_is_empty(self):
        """FR-7.1, FR-7.2"""
        before = timezone.now()
        visitor = make_visitor(self.student)
        self.assertGreaterEqual(visitor.entered_at, before)
        self.assertLessEqual(visitor.entered_at, timezone.now())
        self.assertIsNone(visitor.exited_at)
        self.assertTrue(visitor.on_premises)

    def test_form_has_no_host_or_time_fields(self):
        """Host and times cannot be typed in (NFR-3, FR-7.2)."""
        self.assertEqual(list(VisitorForm().fields), ["name", "phone", "purpose"])

    def test_host_without_a_room_is_refused(self):
        """FR-7.5 / TC-10"""
        roomless = make_user("PES1UG23CS902")
        with self.assertRaises(ValidationError):
            Visitor(host=roomless, name="Ann", phone="9123456780", purpose="Visit").full_clean()

    def test_host_with_a_room_is_accepted(self):
        Visitor(host=self.student, name="Ann", phone="9123456780", purpose="Visit").full_clean()

    def test_bad_phone_is_rejected(self):
        with self.assertRaises(ValidationError) as caught:
            Visitor(host=self.student, name="Ann", phone="abc", purpose="Visit").full_clean()
        self.assertIn("phone", caught.exception.message_dict)

    def test_check_out_records_the_server_exit_time(self):
        """FR-7.3"""
        visitor = make_visitor(self.student)
        visitor.check_out()
        self.assertIsNotNone(visitor.exited_at)
        self.assertGreaterEqual(visitor.exited_at, visitor.entered_at)
        self.assertFalse(visitor.on_premises)

    def test_checking_out_twice_is_rejected_and_keeps_the_first_exit_time(self):
        visitor = make_visitor(self.student)
        visitor.check_out()
        first_exit = visitor.exited_at
        with self.assertRaises(ValidationError):
            visitor.check_out()
        visitor.refresh_from_db()
        self.assertEqual(visitor.exited_at, first_exit)

    def test_second_admin_with_a_stale_copy_cannot_overwrite_the_exit_time(self):
        """Two admins at once: both loaded the visitor as still inside."""
        visitor = make_visitor(self.student)
        admin_one = Visitor.objects.get(pk=visitor.pk)
        admin_two = Visitor.objects.get(pk=visitor.pk)
        admin_one.check_out()
        with self.assertRaises(ValidationError):
            admin_two.check_out()
        visitor.refresh_from_db()
        self.assertEqual(visitor.exited_at, admin_one.exited_at)

    def test_filter_columns_are_indexed(self):
        names = {index.name for index in Visitor._meta.indexes}
        self.assertEqual(names, {"visitor_exited_idx", "visitor_entered_idx"})
