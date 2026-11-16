from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from complaints.models import Complaint
from rooms.models import Room, RoomApplication
from visitors.models import Visitor


class SeedStoryTests(TestCase):
    def test_seeds_every_area_and_is_rerunnable(self):
        for _ in range(2):
            call_command("seed_story", stdout=StringIO())
        self.assertEqual(Room.objects.count(), 7)
        self.assertEqual(RoomApplication.objects.filter(status="pending").count(), 2)
        self.assertEqual(Complaint.objects.count(), 5)
        self.assertEqual(Visitor.objects.filter(exited_at__isnull=True).count(), 2)
        for r in Room.objects.all():
            r.full_clean()
        # Admin and student pages load with the seeded data (right URLs, right roles).
        self.assertTrue(self.client.login(srn="DEMOADMIN01", password="Demo@12345"))
        for url in ["/dashboard/admin/", "/complaints/manage/", "/visitors/manage/", "/fees/manage/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.client.logout()
        self.assertTrue(self.client.login(srn="PES1UG24CS001", password="Demo@12345"))
        for url in ["/dashboard/student/", "/complaints/", "/visitors/", "/fees/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
