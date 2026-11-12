"""Integration tests: URL -> view -> form -> model -> database, with role checks (FR-7, NFR-3)."""

from django.test import Client, TestCase
from django.urls import reverse

from visitors.models import Visitor

from .helpers import allot_room, make_admin, make_user


class VisitorViewTestCase(TestCase):
    def setUp(self):
        self.admin_user = make_admin()
        self.student = make_user("PES1UG23CS811", first_name="Asha")
        self.room = allot_room(self.student)
        self.unallotted_student = make_user("PES1UG23CS812", first_name="Ravi")

    def register_visitor(self, client, follow=False, **overrides):
        data = {"name": "Ramesh", "contact_number": "9812345678", "purpose": "Family visit"}
        data.update(overrides)
        return client.post(reverse("visitors:register"), data, follow=follow)

    def admin_client(self):
        client = Client()
        client.force_login(self.admin_user)
        return client


class StudentRegistrationTests(VisitorViewTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.student)

    def test_student_with_a_room_registers_a_visitor(self):  # FR-7.1, FR-7.2
        response = self.register_visitor(self.client, follow=True)

        self.assertRedirects(response, reverse("visitors:my-visitors"))
        visitor = Visitor.objects.get()
        self.assertEqual(visitor.host, self.student)
        self.assertEqual(visitor.name, "Ramesh")
        self.assertTrue(visitor.is_inside)
        self.assertContains(response, "Ramesh has been registered as your visitor.")

    def test_entry_time_comes_from_the_server_not_the_form(self):
        self.register_visitor(self.client, entry_time="2001-01-01 00:00:00", host=self.unallotted_student.pk)

        visitor = Visitor.objects.get()
        self.assertNotEqual(visitor.entry_time.isoformat(), "2001-01-01 00:00:00")
        self.assertEqual(visitor.host, self.student)
        self.assertFalse(self.unallotted_student.visitors.exists())

    def test_student_without_a_room_cannot_register_a_visitor(self):  # TC-10 (FR-7.5)
        self.client.force_login(self.unallotted_student)

        get_response = self.client.get(reverse("visitors:register"))
        post_response = self.register_visitor(self.client)

        self.assertRedirects(get_response, reverse("student-dashboard"))
        self.assertRedirects(post_response, reverse("student-dashboard"))
        self.assertFalse(Visitor.objects.exists())

    def test_invalid_form_shows_errors_keeps_input_and_saves_nothing(self):
        response = self.register_visitor(self.client, name="", purpose="")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.assertContains(response, 'value="9812345678"')
        self.assertFalse(Visitor.objects.exists())

    def test_purpose_boundary_200_accepted_201_rejected(self):
        accepted = self.register_visitor(self.client, purpose="x" * 200)
        rejected = self.register_visitor(self.client, name="Suresh", purpose="y" * 201)

        self.assertEqual(accepted.status_code, 302)
        self.assertEqual(rejected.status_code, 200)
        self.assertContains(rejected, "at most 200 characters")
        self.assertEqual(Visitor.objects.count(), 1)

    def test_student_sees_only_their_own_visitors(self):
        self.register_visitor(self.client)
        other = make_user("PES1UG23CS813")
        allot_room(other, room_number="102")
        Visitor.objects.create(name="Mahesh", contact_number="9899999999", purpose="Friend", host=other)

        response = self.client.get(reverse("visitors:my-visitors"))

        self.assertContains(response, "Ramesh")
        self.assertNotContains(response, "Mahesh")

    def test_empty_list_shows_a_message(self):
        response = self.client.get(reverse("visitors:my-visitors"))

        self.assertContains(response, "You have not registered any visitors yet.")

    def test_anonymous_user_is_sent_to_login(self):
        client = Client()

        response = client.get(reverse("visitors:register"))

        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('visitors:register')}"
        )


class AdminVisitorTests(VisitorViewTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin_user)
        self.visitor = Visitor.objects.create(
            name="Ramesh", contact_number="9812345678", purpose="Family visit", host=self.student
        )
        self.checked_out = Visitor.objects.create(
            name="Mahesh", contact_number="9899999999", purpose="Friend", host=self.student
        )
        self.checked_out.check_out()

    def test_admin_sees_visitor_records_with_entry_exit_status(self):  # FR-7.1, FR-7.4
        response = self.client.get(reverse("visitors:visitor-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ramesh")
        self.assertContains(response, "Mahesh")
        self.assertContains(response, "PES1UG23CS811")
        self.assertContains(response, "Inside")
        self.assertContains(response, "Checked out")

    def test_inside_filter_lists_only_visitors_on_the_premises(self):  # FR-7.4
        response = self.client.get(reverse("visitors:visitor-list"), {"presence": "inside"})

        self.assertContains(response, "Ramesh")
        self.assertNotContains(response, "Mahesh")

    def test_checked_out_filter_lists_only_departed_visitors(self):
        response = self.client.get(reverse("visitors:visitor-list"), {"presence": "checked_out"})

        self.assertContains(response, "Mahesh")
        self.assertNotContains(response, "Ramesh")

    def test_invalid_filter_value_is_ignored(self):
        response = self.client.get(reverse("visitors:visitor-list"), {"presence": "everywhere"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ramesh")
        self.assertContains(response, "Mahesh")

    def test_admin_check_out_records_the_server_exit_time(self):  # FR-7.3
        response = self.client.post(
            reverse("visitors:check-out", args=[self.visitor.pk]),
            {"exit_time": "2001-01-01 00:00:00"},
            follow=True,
        )

        self.assertRedirects(response, reverse("visitors:visitor-list"))
        self.visitor.refresh_from_db()
        self.assertFalse(self.visitor.is_inside)
        self.assertNotEqual(self.visitor.exit_time.isoformat(), "2001-01-01 00:00:00")
        self.assertContains(response, "Ramesh has been checked out.")

    def test_checked_out_visitor_leaves_the_inside_list(self):
        self.client.post(reverse("visitors:check-out", args=[self.visitor.pk]))

        response = self.client.get(reverse("visitors:visitor-list"), {"presence": "inside"})

        self.assertFalse(response.context["visitors"])
        self.assertContains(response, "No visitors match this filter.")

    def test_checking_out_twice_shows_an_error(self):
        self.client.post(reverse("visitors:check-out", args=[self.visitor.pk]))
        response = self.client.post(reverse("visitors:check-out", args=[self.visitor.pk]), follow=True)

        self.assertContains(response, "Ramesh has already checked out.")

    def test_unknown_visitor_checkout_is_404(self):
        response = self.client.post(reverse("visitors:check-out", args=[99999]))

        self.assertEqual(response.status_code, 404)

    def test_students_cannot_use_admin_visitor_pages(self):  # NFR-3
        client = Client()
        client.force_login(self.student)

        list_response = client.get(reverse("visitors:visitor-list"))
        checkout_response = client.post(reverse("visitors:check-out", args=[self.visitor.pk]))

        self.assertEqual(list_response.status_code, 403)
        self.assertEqual(checkout_response.status_code, 403)
        self.visitor.refresh_from_db()
        self.assertTrue(self.visitor.is_inside)

    def test_checkout_requires_post(self):
        response = self.client.get(reverse("visitors:check-out", args=[self.visitor.pk]))

        self.assertEqual(response.status_code, 405)
