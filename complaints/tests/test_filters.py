"""Complaint filters for admins (FR-9.3) and students' own complaints (FR-9.4, FR-9.5)."""

from django.test import TestCase
from django.urls import reverse

from complaints.models import Complaint

from .helpers import make_admin, make_complaint, make_user

Category = Complaint.Category
Status = Complaint.Status


class ComplaintFilterTestCase(TestCase):
    def setUp(self):
        self.admin_user = make_admin()
        self.student = make_user("PES1UG23CS801", first_name="Asha")
        self.other_student = make_user("PES1UG23CS802", first_name="Ravi")
        self.open_plumbing = make_complaint(self.student, description="Asha tap leaking.")
        self.resolved_internet = make_complaint(
            self.student,
            category=Category.INTERNET,
            description="Asha wifi down.",
            status=Status.RESOLVED,
        )
        self.other_open_internet = make_complaint(
            self.other_student, category=Category.INTERNET, description="Ravi wifi slow."
        )


class AdminComplaintFilterTests(ComplaintFilterTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin_user)
        self.url = reverse("complaints:complaint-list")

    def test_filter_by_status(self):
        response = self.client.get(self.url, {"status": Status.OPEN})

        self.assertEqual(
            set(response.context["complaints"]), {self.open_plumbing, self.other_open_internet}
        )

    def test_filter_by_category(self):
        response = self.client.get(self.url, {"category": Category.INTERNET})

        self.assertEqual(
            set(response.context["complaints"]),
            {self.resolved_internet, self.other_open_internet},
        )

    def test_status_and_category_combine(self):
        response = self.client.get(
            self.url, {"status": Status.OPEN, "category": Category.INTERNET}
        )

        self.assertEqual(list(response.context["complaints"]), [self.other_open_internet])

    def test_no_filters_lists_everything(self):
        response = self.client.get(self.url)

        self.assertEqual(response.context["complaints"].count(), 3)
        self.assertNotContains(response, "No results found")

    def test_no_matches_shows_message_not_error(self):
        response = self.client.get(self.url, {"category": Category.FURNITURE})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No results found")

    def test_unknown_filter_value_is_ignored_with_a_field_error(self):
        response = self.client.get(self.url, {"status": "deleted", "category": Category.PLUMBING})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["complaints"]), [self.open_plumbing])
        self.assertContains(response, "Select a valid choice")

    def test_filters_are_kept_in_the_form_after_searching(self):
        response = self.client.get(self.url, {"status": Status.OPEN})

        self.assertContains(response, '<option value="open" selected>')
        self.assertContains(response, "Clear")


class StudentComplaintFilterTests(ComplaintFilterTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.student)
        self.url = reverse("complaints:my-complaints")

    def test_student_filter_only_searches_their_own_complaints(self):
        response = self.client.get(self.url, {"category": Category.INTERNET})

        self.assertEqual(list(response.context["complaints"]), [self.resolved_internet])
        self.assertNotContains(response, "Ravi wifi slow.")

    def test_student_status_filter(self):
        response = self.client.get(self.url, {"status": Status.OPEN})

        self.assertEqual(list(response.context["complaints"]), [self.open_plumbing])

    def test_student_no_matches_shows_message(self):
        response = self.client.get(self.url, {"status": Status.IN_PROGRESS})

        self.assertContains(response, "No results found")

    def test_student_cannot_use_admin_complaint_filters(self):
        response = self.client.get(
            reverse("complaints:complaint-list"), {"category": Category.INTERNET}
        )

        self.assertEqual(response.status_code, 403)
