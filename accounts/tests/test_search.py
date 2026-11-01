"""Admin student search by partial name or SRN (FR-9.1, FR-9.4)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class StudentSearchTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin_user = User.objects.create_user(
            srn="PES1UG23AD901", email="search.admin@example.com", password="admin-password",
            first_name="Search", last_name="Admin", contact_number="9876543299",
            role=User.Role.ADMIN,
        )
        self.asha = self.make_student("PES1UG23CS901", "Asha", "Rao")
        self.ravi = self.make_student("PES1UG23EC902", "Ravi", "Kumar")
        self.ashwin = self.make_student("PES1UG23ME903", "Ashwin", "Nair")
        self.client.force_login(self.admin_user)
        self.url = reverse("student-list")

    def make_student(self, srn, first_name, last_name):
        return get_user_model().objects.create_user(
            srn=srn, email=f"{srn.lower()}@example.com", password="student-password",
            first_name=first_name, last_name=last_name, contact_number="9876543200",
        )

    def search(self, query):
        response = self.client.get(self.url, {"q": query})
        self.assertEqual(response.status_code, 200)
        return set(response.context["students"])

    def test_partial_first_name_matches(self):
        self.assertEqual(self.search("ash"), {self.asha, self.ashwin})

    def test_last_name_matches(self):
        self.assertEqual(self.search("kumar"), {self.ravi})

    def test_full_name_matches(self):
        self.assertEqual(self.search("Asha Rao"), {self.asha})

    def test_extra_spaces_are_ignored(self):
        self.assertEqual(self.search("  asha   rao "), {self.asha})

    def test_partial_srn_matches_case_insensitively(self):
        self.assertEqual(self.search("ug23ec"), {self.ravi})

    def test_full_srn_matches(self):
        self.assertEqual(self.search("PES1UG23ME903"), {self.ashwin})

    def test_admins_are_never_returned(self):
        self.assertEqual(self.search("admin"), set())

    def test_empty_search_lists_all_students(self):
        self.assertEqual(self.search(""), {self.asha, self.ravi, self.ashwin})

    def test_no_matches_shows_message_not_error(self):
        response = self.client.get(self.url, {"q": "zzz"})

        self.assertContains(response, "No results found for")

    def test_special_characters_are_treated_as_text(self):
        for query in ("%", "_", "' OR 1=1 --", "<script>"):
            with self.subTest(query=query):
                response = self.client.get(self.url, {"q": query})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.context["students"]), 0)
        self.assertNotContains(response, "<script>")

    def test_overlong_query_is_a_form_error_not_a_crash(self):
        response = self.client.get(self.url, {"q": "a" * 200})

        self.assertEqual(response.status_code, 200)
        self.assertIn("q", response.context["search_form"].errors)

    def test_student_cannot_search_student_records(self):
        self.client.force_login(self.asha)

        self.assertEqual(self.client.get(self.url, {"q": "ravi"}).status_code, 403)
