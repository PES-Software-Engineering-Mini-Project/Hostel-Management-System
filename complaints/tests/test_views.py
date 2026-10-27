"""Integration tests: URL -> view -> form -> model -> database, with role checks (FR-6, NFR-3)."""

from datetime import timedelta

from django.conf import settings
from django.shortcuts import resolve_url
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from complaints.models import Complaint

from .helpers import make_admin, make_complaint, make_user

Status = Complaint.Status


class ComplaintViewTestCase(TestCase):
    def setUp(self):
        self.admin_user = make_admin()
        self.student = make_user("PES1UG23CS701", first_name="Asha")
        self.other_student = make_user("PES1UG23CS702", first_name="Ravi")
        self.complaint = make_complaint(self.student, description="Asha's leaking tap.")
        self.other_complaint = make_complaint(
            self.other_student,
            category=Complaint.Category.INTERNET,
            description="Ravi's slow wifi.",
        )

    def status_url(self, complaint):
        return reverse("complaints:update-status", args=[complaint.pk])

    def detail_url(self, complaint):
        return reverse("complaints:detail", args=[complaint.pk])

    def admin_client(self):
        client = Client()
        client.force_login(self.admin_user)
        return client


class StudentComplaintTests(ComplaintViewTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.student)

    def test_raise_form_is_shown_with_the_500_character_limit(self):
        response = self.client.get(reverse("complaints:raise"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'maxlength="500"')

    def test_student_raises_complaint_saved_as_open_and_listed(self):  # TC-08
        response = self.client.post(
            reverse("complaints:raise"),
            {"category": "electrical", "description": "Fan is not working."},
            follow=True,
        )

        self.assertRedirects(response, reverse("complaints:my-complaints"))
        complaint = Complaint.objects.get(description="Fan is not working.")
        self.assertEqual(complaint.status, Status.OPEN)
        self.assertEqual(complaint.student, self.student)
        self.assertContains(response, "Fan is not working.")
        self.assertContains(response, "Your complaint has been submitted.")

    def test_forged_status_and_student_in_the_post_are_ignored(self):
        self.client.post(
            reverse("complaints:raise"),
            {
                "category": "cleaning",
                "description": "Forged request.",
                "status": "resolved",
                "student": self.other_student.pk,
            },
        )

        complaint = Complaint.objects.get(description="Forged request.")
        self.assertEqual(complaint.status, Status.OPEN)
        self.assertEqual(complaint.student, self.student)
        self.assertFalse(self.other_student.complaints.filter(description="Forged request.").exists())

    def test_invalid_complaint_shows_errors_keeps_input_and_saves_nothing(self):
        before = Complaint.objects.count()

        response = self.client.post(
            reverse("complaints:raise"), {"category": "plumbing", "description": ""}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.assertContains(response, '<option value="plumbing" selected>')
        self.assertEqual(Complaint.objects.count(), before)

    def test_unknown_category_is_rejected(self):
        before = Complaint.objects.count()

        response = self.client.post(
            reverse("complaints:raise"), {"category": "gym", "description": "Broken."}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice.")
        self.assertEqual(Complaint.objects.count(), before)

    def test_description_boundary_500_accepted_501_rejected(self):
        before = Complaint.objects.count()

        accepted = self.client.post(
            reverse("complaints:raise"), {"category": "other", "description": "x" * 500}
        )
        rejected = self.client.post(
            reverse("complaints:raise"), {"category": "other", "description": "y" * 501}
        )

        self.assertEqual(accepted.status_code, 302)
        self.assertEqual(rejected.status_code, 200)
        self.assertContains(rejected, "at most 500 characters")
        self.assertEqual(Complaint.objects.count(), before + 1)
        self.assertFalse(Complaint.objects.filter(description__startswith="y").exists())

    def test_student_sees_only_their_own_complaints(self):
        response = self.client.get(reverse("complaints:my-complaints"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Asha&#x27;s leaking tap.")
        self.assertNotContains(response, "Ravi")
        self.assertNotContains(response, "slow wifi")

    def test_empty_list_shows_a_message(self):
        self.client.force_login(make_user("PES1UG23CS703"))

        response = self.client.get(reverse("complaints:my-complaints"))

        self.assertContains(response, "You have not raised any complaints yet.")

    def test_student_opens_their_own_complaint(self):
        response = self.client.get(self.detail_url(self.complaint))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Asha&#x27;s leaking tap.")

    def test_other_students_complaint_is_404_by_url_and_missing_from_the_list(self):  # TC-12
        detail = self.client.get(self.detail_url(self.other_complaint))
        listing = self.client.get(reverse("complaints:my-complaints"))

        self.assertEqual(detail.status_code, 404)
        self.assertNotContains(detail, "slow wifi", status_code=404)
        self.assertNotContains(listing, "slow wifi")

    def test_unknown_complaint_is_404(self):
        response = self.client.get(reverse("complaints:detail", args=[99999]))

        self.assertEqual(response.status_code, 404)

    def test_student_cannot_change_status_of_their_own_complaint(self):  # TC-09
        for status in ("in_progress", "resolved"):
            with self.subTest(status=status):
                response = self.client.post(self.status_url(self.complaint), {"status": status})

                self.assertEqual(response.status_code, 403)
                self.complaint.refresh_from_db()
                self.assertEqual(self.complaint.status, Status.OPEN)

    def test_student_cannot_change_status_of_another_students_complaint(self):
        response = self.client.post(self.status_url(self.other_complaint), {"status": "resolved"})

        self.assertEqual(response.status_code, 403)
        self.other_complaint.refresh_from_db()
        self.assertEqual(self.other_complaint.status, Status.OPEN)

    def test_student_gets_403_on_status_url_and_admin_list(self):
        for url in (self.status_url(self.complaint), reverse("complaints:complaint-list")):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_student_sees_new_status_after_admin_moves_it(self):
        admin = self.admin_client()

        admin.post(self.status_url(self.complaint), {"status": "in_progress"})
        in_progress = self.client.get(self.detail_url(self.complaint))
        admin.post(self.status_url(self.complaint), {"status": "resolved"})
        resolved = self.client.get(self.detail_url(self.complaint))
        listing = self.client.get(reverse("complaints:my-complaints"))

        self.assertContains(in_progress, ">In Progress</span>")
        self.assertContains(resolved, ">Resolved</span>")
        self.assertContains(listing, ">Resolved</span>")


class AdminComplaintTests(ComplaintViewTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin_user)

    def test_admin_list_shows_every_students_complaints(self):
        response = self.client.get(reverse("complaints:complaint-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PES1UG23CS701")
        self.assertContains(response, "PES1UG23CS702")
        self.assertContains(response, "Asha&#x27;s leaking tap.")
        self.assertContains(response, "Ravi&#x27;s slow wifi.")

    def test_admin_list_is_newest_first(self):
        Complaint.objects.filter(pk=self.complaint.pk).update(
            raised_at=timezone.now() - timedelta(days=2)
        )

        response = self.client.get(reverse("complaints:complaint-list"))

        self.assertEqual(
            [c.pk for c in response.context["complaints"]],
            [self.other_complaint.pk, self.complaint.pk],
        )

    def test_admin_moves_complaint_open_to_in_progress_to_resolved(self):
        first = self.client.post(
            self.status_url(self.complaint), {"status": "in_progress"}, follow=True
        )
        self.complaint.refresh_from_db()
        self.assertRedirects(first, reverse("complaints:complaint-list"))
        self.assertEqual(self.complaint.status, Status.IN_PROGRESS)
        self.assertContains(first, f"Complaint #{self.complaint.pk} is now In Progress.")

        second = self.client.post(
            self.status_url(self.complaint), {"status": "resolved"}, follow=True
        )
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, Status.RESOLVED)
        self.assertContains(second, f"Complaint #{self.complaint.pk} is now Resolved.")

    def test_only_the_next_action_button_is_offered(self):
        open_page = self.client.get(reverse("complaints:complaint-list"))
        self.assertContains(open_page, "Start work")
        self.assertNotContains(open_page, "Mark resolved")

        self.complaint.change_status(Status.IN_PROGRESS)
        self.other_complaint.change_status(Status.IN_PROGRESS)
        progress_page = self.client.get(reverse("complaints:complaint-list"))
        self.assertContains(progress_page, "Mark resolved")
        self.assertNotContains(progress_page, "Start work")

        self.complaint.change_status(Status.RESOLVED)
        self.other_complaint.change_status(Status.RESOLVED)
        resolved_page = self.client.get(reverse("complaints:complaint-list"))
        self.assertNotContains(resolved_page, "Start work")
        self.assertNotContains(resolved_page, "Mark resolved")

    def test_skipping_a_step_is_rejected_with_a_message(self):
        response = self.client.post(
            self.status_url(self.complaint), {"status": "resolved"}, follow=True
        )

        self.assertRedirects(response, reverse("complaints:complaint-list"))
        self.assertContains(response, "cannot move from Open to Resolved")
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, Status.OPEN)

    def test_backwards_and_repeated_status_are_rejected(self):
        self.complaint.change_status(Status.IN_PROGRESS)
        for status in ("open", "in_progress"):
            with self.subTest(status=status):
                response = self.client.post(self.status_url(self.complaint), {"status": status})

                self.assertEqual(response.status_code, 302)
                self.complaint.refresh_from_db()
                self.assertEqual(self.complaint.status, Status.IN_PROGRESS)

    def test_resolved_complaint_cannot_change_and_never_crashes(self):
        self.complaint.change_status(Status.IN_PROGRESS)
        self.complaint.change_status(Status.RESOLVED)
        for data in (
            {"status": "in_progress"},  # valid value
            {"status": "open"},
            {"status": "resolved"},
            {"status": ""},  # empty value
            {"status": "bogus"},  # invalid value
            {},  # no status field at all
        ):
            with self.subTest(data=data):
                response = self.client.post(self.status_url(self.complaint), data)

                self.assertEqual(response.status_code, 302)
                self.complaint.refresh_from_db()
                self.assertEqual(self.complaint.status, Status.RESOLVED)

    def test_empty_missing_and_invalid_status_are_rejected_for_open_complaint(self):
        for data in ({"status": ""}, {"status": "bogus"}, {}):
            with self.subTest(data=data):
                response = self.client.post(self.status_url(self.complaint), data)

                self.assertEqual(response.status_code, 302)
                self.complaint.refresh_from_db()
                self.assertEqual(self.complaint.status, Status.OPEN)

    def test_get_on_status_url_is_405(self):
        response = self.client.get(self.status_url(self.complaint))

        self.assertEqual(response.status_code, 405)

    def test_unknown_complaint_status_update_is_404(self):
        response = self.client.post(
            reverse("complaints:update-status", args=[99999]), {"status": "in_progress"}
        )

        self.assertEqual(response.status_code, 404)

    def test_admin_opening_a_student_detail_url_is_403(self):
        response = self.client.get(self.detail_url(self.complaint))

        self.assertEqual(response.status_code, 403)

    def test_admin_cannot_use_student_pages(self):
        for url in (reverse("complaints:raise"), reverse("complaints:my-complaints")):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_admin_cannot_raise_a_complaint(self):
        before = Complaint.objects.count()

        response = self.client.post(
            reverse("complaints:raise"), {"category": "other", "description": "Admin complaint."}
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Complaint.objects.count(), before)


class AnonymousComplaintAccessTests(ComplaintViewTestCase):
    def test_logged_out_users_are_sent_to_login(self):
        urls = (
            reverse("complaints:my-complaints"),
            reverse("complaints:raise"),
            self.detail_url(self.complaint),
            reverse("complaints:complaint-list"),
        )
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(
                    response,
                    f"{resolve_url(settings.LOGIN_URL)}?next={url}",
                    fetch_redirect_response=False,
                )

    def test_logged_out_post_to_status_url_is_sent_to_login_and_changes_nothing(self):
        url = self.status_url(self.complaint)

        response = self.client.post(url, {"status": "in_progress"})

        self.assertRedirects(
            response,
            f"{resolve_url(settings.LOGIN_URL)}?next={url}",
            fetch_redirect_response=False,
        )
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, Status.OPEN)


class DashboardLinkTests(ComplaintViewTestCase):
    def test_student_dashboard_links_to_complaint_pages(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("student-dashboard"))

        self.assertContains(response, reverse("complaints:raise"))
        self.assertContains(response, reverse("complaints:my-complaints"))

    def test_admin_dashboard_links_to_complaint_management(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin-dashboard"))

        self.assertContains(response, reverse("complaints:complaint-list"))
