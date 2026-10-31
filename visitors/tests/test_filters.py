"""FR-7.4: the admin lists visitors still on the premises. FR-9.4: empty result is a message."""

from django.test import Client, TestCase
from django.urls import reverse

from .helpers import give_room, make_admin, make_user, make_visitor


class VisitorFilterTests(TestCase):
    def setUp(self):
        self.admin_user = make_admin()
        asha = make_user("PES1UG23CS921", first_name="Asha")
        ravi = make_user("PES1UG23CS922", first_name="Ravi")
        give_room(asha, "101")
        give_room(ravi, "102")
        self.inside = make_visitor(asha, name="Inside Person")
        self.left = make_visitor(ravi, name="Departed Person")
        self.left.check_out()
        self.client = Client()
        self.client.force_login(self.admin_user)
        self.url = reverse("visitors:visitor-list")

    def test_on_premises_shows_only_visitors_without_an_exit(self):
        response = self.client.get(self.url, {"status": "inside"})
        self.assertContains(response, "Inside Person")
        self.assertNotContains(response, "Departed Person")

    def test_checked_out_filter(self):
        response = self.client.get(self.url, {"status": "left"})
        self.assertContains(response, "Departed Person")
        self.assertNotContains(response, "Inside Person")

    def test_search_by_visitor_name_or_host_srn(self):
        self.assertNotContains(self.client.get(self.url, {"q": "departed"}), "Inside Person")
        self.assertContains(self.client.get(self.url, {"q": "PES1UG23CS921"}), "Inside Person")

    def test_no_match_shows_a_message_not_an_error(self):
        response = self.client.get(self.url, {"q": "nobody-here"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No results found")

    def test_invalid_status_is_ignored(self):
        response = self.client.get(self.url, {"status": "bogus"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inside Person")
