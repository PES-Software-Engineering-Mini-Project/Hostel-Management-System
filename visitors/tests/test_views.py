"""Integration tests: URL -> view -> form -> model, with role checks (FR-7, NFR-3)."""

from django.test import Client, TestCase
from django.urls import reverse

from visitors.models import Visitor

from .helpers import give_room, make_admin, make_user, make_visitor

DATA = {"name": "Meera Rao", "phone": "9123456780", "purpose": "Family visit"}


class VisitorViewTestCase(TestCase):
    def setUp(self):
        self.admin_user = make_admin()
        self.student = make_user("PES1UG23CS911", first_name="Asha")
        self.other_student = make_user("PES1UG23CS912", first_name="Ravi")
        give_room(self.student, "101")
        give_room(self.other_student, "102")

    def login(self, user):
        client = Client()
        client.force_login(user)
        return client


class RegisterVisitorTests(VisitorViewTestCase):
    def test_student_with_a_room_registers_a_visitor(self):
        """FR-7.1, FR-7.2: host is the logged-in student, entry time is the server's."""
        response = self.login(self.student).post(reverse("visitors:register"), DATA)
        self.assertRedirects(response, reverse("visitors:my-visitors"))
        visitor = Visitor.objects.get()
        self.assertEqual(visitor.host, self.student)
        self.assertIsNotNone(visitor.entered_at)
        self.assertIsNone(visitor.exited_at)

    def test_forged_host_and_times_in_the_post_are_ignored(self):
        """NFR-3, FR-7.2"""
        self.login(self.student).post(
            reverse("visitors:register"),
            {**DATA, "host": self.other_student.pk, "entered_at": "2000-01-01 00:00",
             "exited_at": "2000-01-02 00:00"},
        )
        visitor = Visitor.objects.get()
        self.assertEqual(visitor.host, self.student)
        self.assertGreater(visitor.entered_at.year, 2000)
        self.assertIsNone(visitor.exited_at)

    def test_student_without_a_room_is_refused(self):
        """FR-7.5 / TC-10: visitor logged against a student with no room is rejected."""
        roomless = make_user("PES1UG23CS913")
        client = self.login(roomless)
        response = client.post(reverse("visitors:register"), DATA)
        self.assertEqual(response.status_code, 200)  # form shown again, nothing saved
        self.assertFalse(Visitor.objects.exists())
        self.assertContains(client.get(reverse("visitors:register")), "only after you have been allotted a room")

    def test_invalid_input_keeps_what_was_typed(self):
        response = self.login(self.student).post(
            reverse("visitors:register"), {**DATA, "phone": "abc"}
        )
        self.assertContains(response, "Meera Rao")
        self.assertContains(response, "Enter a phone number")
        self.assertFalse(Visitor.objects.exists())


class StudentListTests(VisitorViewTestCase):
    def test_student_sees_only_their_own_visitors(self):
        """NFR-3"""
        make_visitor(self.student, name="Asha's guest")
        make_visitor(self.other_student, name="Ravi's guest")
        response = self.login(self.student).get(reverse("visitors:my-visitors"))
        self.assertContains(response, "Asha&#x27;s guest")
        self.assertNotContains(response, "Ravi&#x27;s guest")

    def test_empty_state(self):
        response = self.login(self.student).get(reverse("visitors:my-visitors"))
        self.assertContains(response, "not registered any visitors")


class AdminLogTests(VisitorViewTestCase):
    def test_admin_sees_every_visitor(self):
        make_visitor(self.student, name="Guest One")
        make_visitor(self.other_student, name="Guest Two")
        response = self.login(self.admin_user).get(reverse("visitors:visitor-list"))
        self.assertContains(response, "Guest One")
        self.assertContains(response, "Guest Two")

    def test_admin_checks_a_visitor_out(self):
        """FR-7.3"""
        visitor = make_visitor(self.student)
        response = self.login(self.admin_user).post(reverse("visitors:check-out", args=[visitor.pk]))
        self.assertRedirects(response, reverse("visitors:visitor-list"))
        visitor.refresh_from_db()
        self.assertIsNotNone(visitor.exited_at)

    def test_second_checkout_is_rejected_with_a_message(self):
        visitor = make_visitor(self.student)
        client = self.login(self.admin_user)
        url = reverse("visitors:check-out", args=[visitor.pk])
        client.post(url)
        first_exit = Visitor.objects.get().exited_at
        response = client.post(url, follow=True)
        self.assertContains(response, "already been checked out")
        self.assertEqual(Visitor.objects.get().exited_at, first_exit)

    def test_checkout_needs_post(self):
        visitor = make_visitor(self.student)
        response = self.login(self.admin_user).get(reverse("visitors:check-out", args=[visitor.pk]))
        self.assertEqual(response.status_code, 405)

    def test_checkout_of_a_missing_visitor_is_404(self):
        response = self.login(self.admin_user).post(reverse("visitors:check-out", args=[9999]))
        self.assertEqual(response.status_code, 404)


class AccessTests(VisitorViewTestCase):
    def test_student_gets_403_on_admin_pages(self):
        """FR-1.3 for the visitor pages."""
        visitor = make_visitor(self.student)
        client = self.login(self.student)
        self.assertEqual(client.get(reverse("visitors:visitor-list")).status_code, 403)
        self.assertEqual(client.post(reverse("visitors:check-out", args=[visitor.pk])).status_code, 403)
        visitor.refresh_from_db()
        self.assertIsNone(visitor.exited_at)

    def test_admin_gets_403_on_student_pages(self):
        client = self.login(self.admin_user)
        self.assertEqual(client.get(reverse("visitors:register")).status_code, 403)
        self.assertEqual(client.get(reverse("visitors:my-visitors")).status_code, 403)

    def test_logged_out_users_are_sent_to_login(self):
        visitor = make_visitor(self.student)
        for url in (
            reverse("visitors:register"), reverse("visitors:my-visitors"),
            reverse("visitors:visitor-list"), reverse("visitors:check-out", args=[visitor.pk]),
        ):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn("login", response["Location"])

    def test_nav_and_dashboard_links(self):
        admin = self.login(self.admin_user)
        for url in (reverse("admin-dashboard"), reverse("visitors:visitor-list")):
            self.assertContains(admin.get(url), reverse("visitors:visitor-list"))
        student = self.login(self.student)
        for url in (reverse("student-dashboard"), reverse("visitors:my-visitors")):
            self.assertContains(student.get(url), reverse("visitors:register"))
