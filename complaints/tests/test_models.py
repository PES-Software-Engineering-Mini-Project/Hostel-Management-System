"""Unit tests for the Complaint model and form (FR-6.1, FR-6.3, FR-6.4; TC-08)."""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from complaints.forms import ComplaintForm
from complaints.models import DESCRIPTION_MAX_LENGTH, Complaint

from .helpers import make_complaint, make_user

Status = Complaint.Status


class ComplaintModelTests(TestCase):
    def setUp(self):
        self.student = make_user("PES1UG23CS701")

    def test_new_complaint_defaults_to_open_with_timestamps(self):  # TC-08
        before = timezone.now()

        complaint = Complaint.objects.create(
            student=self.student, category=Complaint.Category.ELECTRICAL, description="No power."
        )

        self.assertEqual(complaint.status, Status.OPEN)
        self.assertGreaterEqual(complaint.raised_at, before)
        self.assertGreaterEqual(complaint.updated_at, before)

    def test_status_moves_forward_one_step_at_a_time(self):
        complaint = make_complaint(self.student)

        complaint.change_status(Status.IN_PROGRESS)
        self.assertEqual(complaint.status, Status.IN_PROGRESS)
        complaint.change_status(Status.RESOLVED)
        self.assertEqual(complaint.status, Status.RESOLVED)

        complaint.refresh_from_db()
        self.assertEqual(complaint.status, Status.RESOLVED)

    def test_invalid_transitions_are_rejected_and_status_is_unchanged(self):
        cases = [
            (Status.OPEN, Status.RESOLVED),  # skipping a step
            (Status.OPEN, Status.OPEN),  # same status
            (Status.IN_PROGRESS, Status.OPEN),  # going backwards
            (Status.IN_PROGRESS, Status.IN_PROGRESS),
            (Status.RESOLVED, Status.OPEN),
            (Status.RESOLVED, Status.IN_PROGRESS),
            (Status.RESOLVED, Status.RESOLVED),
        ]
        for start, target in cases:
            with self.subTest(start=start, target=target):
                complaint = make_complaint(self.student, status=start)

                with self.assertRaises(ValidationError):
                    complaint.change_status(target)

                complaint.refresh_from_db()
                self.assertEqual(complaint.status, start)

    def test_resolved_complaint_rejects_every_value_without_crashing(self):
        complaint = make_complaint(self.student, status=Status.RESOLVED)

        # A valid value, an empty value, an invalid value, and None (no value at all).
        for value in (Status.IN_PROGRESS, Status.OPEN, "", "bogus", None):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    complaint.change_status(value)

                complaint.refresh_from_db()
                self.assertEqual(complaint.status, Status.RESOLVED)

    def test_empty_and_unknown_values_are_rejected_for_unresolved_complaints(self):
        for start in (Status.OPEN, Status.IN_PROGRESS):
            for value in ("", "bogus", None):
                with self.subTest(start=start, value=value):
                    complaint = make_complaint(self.student, status=start)

                    with self.assertRaises(ValidationError):
                        complaint.change_status(value)

                    complaint.refresh_from_db()
                    self.assertEqual(complaint.status, start)

    def test_updated_at_moves_forward_when_status_changes(self):
        complaint = make_complaint(self.student)
        long_ago = timezone.now() - timedelta(hours=1)
        Complaint.objects.filter(pk=complaint.pk).update(updated_at=long_ago)
        complaint.refresh_from_db()

        complaint.change_status(Status.IN_PROGRESS)

        self.assertGreater(complaint.updated_at, long_ago)  # in memory ...
        stored = Complaint.objects.get(pk=complaint.pk)
        self.assertEqual(stored.updated_at, complaint.updated_at)  # ... and in the database
        self.assertEqual(stored.status, Status.IN_PROGRESS)

    def test_rejected_change_leaves_updated_at_alone(self):
        complaint = make_complaint(self.student)
        long_ago = timezone.now() - timedelta(hours=1)
        Complaint.objects.filter(pk=complaint.pk).update(updated_at=long_ago)
        complaint.refresh_from_db()

        with self.assertRaises(ValidationError):
            complaint.change_status(Status.RESOLVED)

        complaint.refresh_from_db()
        self.assertEqual(complaint.updated_at, long_ago)

    def test_stale_copy_cannot_overwrite_a_newer_change(self):
        complaint = make_complaint(self.student)
        first = Complaint.objects.get(pk=complaint.pk)
        second = Complaint.objects.get(pk=complaint.pk)

        first.change_status(Status.IN_PROGRESS)
        with self.assertRaisesMessage(ValidationError, "changed by someone else"):
            second.change_status(Status.IN_PROGRESS)

        self.assertEqual(second.status, Status.OPEN)  # the stale copy is left untouched
        self.assertEqual(Complaint.objects.get(pk=complaint.pk).status, Status.IN_PROGRESS)

    def test_stale_copy_cannot_undo_a_resolution(self):
        complaint = make_complaint(self.student)
        first = Complaint.objects.get(pk=complaint.pk)
        second = Complaint.objects.get(pk=complaint.pk)

        first.change_status(Status.IN_PROGRESS)
        first.change_status(Status.RESOLVED)
        with self.assertRaises(ValidationError):
            second.change_status(Status.IN_PROGRESS)

        self.assertEqual(Complaint.objects.get(pk=complaint.pk).status, Status.RESOLVED)

    def test_description_of_500_characters_is_valid_and_501_is_not_on_the_model(self):
        make_complaint(self.student, description="x" * DESCRIPTION_MAX_LENGTH).full_clean()

        too_long = Complaint(
            student=self.student,
            category=Complaint.Category.OTHER,
            description="x" * (DESCRIPTION_MAX_LENGTH + 1),
        )
        with self.assertRaises(ValidationError) as caught:
            too_long.full_clean()
        self.assertIn("description", caught.exception.error_dict)

    def test_empty_description_and_unknown_category_are_invalid_on_the_model(self):
        for field, kwargs in (
            ("description", {"category": "other", "description": ""}),
            ("category", {"category": "gym", "description": "Broken."}),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError) as caught:
                    Complaint(student=self.student, **kwargs).full_clean()
                self.assertIn(field, caught.exception.error_dict)


class ComplaintFormTests(TestCase):
    def form(self, **overrides):
        data = {"category": "plumbing", "description": "Tap is leaking."}
        data.update(overrides)
        return ComplaintForm(data)

    def test_valid_data_is_accepted(self):
        self.assertTrue(self.form().is_valid())

    def test_form_only_exposes_category_and_description(self):
        self.assertEqual(list(ComplaintForm().fields), ["category", "description"])

    def test_empty_or_blank_description_is_a_form_error(self):
        for description in ("", "   \n  "):
            with self.subTest(description=description):
                form = self.form(description=description)

                self.assertFalse(form.is_valid())
                self.assertIn("description", form.errors)

    def test_invalid_category_is_a_form_error(self):
        form = self.form(category="gym")

        self.assertFalse(form.is_valid())
        self.assertIn("category", form.errors)

    def test_missing_category_is_a_form_error(self):
        form = self.form(category="")

        self.assertFalse(form.is_valid())
        self.assertIn("category", form.errors)

    def test_description_boundary_500_valid_501_invalid(self):
        self.assertTrue(self.form(description="x" * 500).is_valid())

        form = self.form(description="x" * 501)

        self.assertFalse(form.is_valid())
        self.assertIn("description", form.errors)
