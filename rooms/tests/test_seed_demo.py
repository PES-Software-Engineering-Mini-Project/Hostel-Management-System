from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from accounts.models import User
from rooms.models import Room


class SeedDemoCommandTests(TestCase):
    def test_seed_demo_runs_and_creates_valid_rooms(self):
        call_command(
            "seed_demo",
            blocks=1,
            rooms_per_block=5,
            students=3,
            complaints=2,
            stdout=StringIO(),
        )

        self.assertEqual(Room.objects.count(), 5)
        self.assertEqual(User.objects.filter(role=User.Role.STUDENT).count(), 3)
        for room in Room.objects.all():
            room.full_clean()

    def test_seed_demo_can_be_run_twice(self):
        options = {"blocks": 1, "rooms_per_block": 2, "students": 2, "complaints": 0}
        call_command("seed_demo", stdout=StringIO(), **options)
        call_command("seed_demo", stdout=StringIO(), **options)

        self.assertEqual(Room.objects.count(), 2)
