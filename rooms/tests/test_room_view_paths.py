"""Room page paths not reached by the other room tests (FR-3.1, FR-3.2, FR-4.1, FR-4.4, FR-4.7)."""
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from rooms.models import Block, Room, RoomAllocation, RoomApplication


def message_texts(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


class RoomPageSetup(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            srn="PES2UG24CS911", email="admin911@example.com", password="Pass12345!",
            role=User.Role.ADMIN, is_staff=True,
        )
        self.student = User.objects.create_user(
            srn="PES2UG24CS912", email="student912@example.com", password="Pass12345!",
            role=User.Role.STUDENT,
        )
        self.block = Block.objects.create(name="Path Block", number_of_floors=2)
        self.room = Room.objects.create(
            block=self.block, room_number="101", floor=1, room_type=Room.RoomType.DOUBLE,
            capacity=2, monthly_fee=1500, occupied_count=0,
        )


class AdminRoomFormTests(RoomPageSetup):
    def test_admin_creates_a_room_through_the_hms_page(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("rooms:room-create"), {
            "block": self.block.pk, "room_number": "102", "floor": 2,
            "room_type": Room.RoomType.SINGLE, "capacity": 1, "monthly_fee": "2000",
        })
        self.assertRedirects(response, reverse("rooms:room-list"))
        self.assertTrue(Room.objects.filter(block=self.block, room_number="102").exists())

    def test_invalid_room_form_shows_errors_and_saves_nothing(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("rooms:room-create"), {
            "block": self.block.pk, "room_number": "103", "floor": 9,
            "room_type": Room.RoomType.SINGLE, "capacity": 1, "monthly_fee": "2000",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(Room.objects.filter(room_number="103").exists())

    def test_invalid_block_form_shows_errors_and_saves_nothing(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("rooms:block-create"), {"name": "", "number_of_floors": 2})
        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["form"].errors)
        self.assertEqual(Block.objects.count(), 1)


class ApplyPageTests(RoomPageSetup):
    def test_student_sees_the_empty_application_form(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("rooms:apply"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)

    def test_invalid_application_shows_errors_and_saves_nothing(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse("rooms:apply"), {"preferred_block": 999999})
        self.assertEqual(response.status_code, 200)
        self.assertIn("preferred_block", response.context["form"].errors)
        self.assertFalse(RoomApplication.objects.filter(student=self.student).exists())

    def test_student_who_already_has_a_room_is_sent_back(self):
        RoomAllocation.objects.create(student=self.student, room=self.room)
        self.client.force_login(self.student)
        response = self.client.get(reverse("rooms:apply"))
        self.assertRedirects(response, reverse("student-dashboard"))
        self.assertIn("You already have an allotted room.", message_texts(response))


class MoveAndAllotEdgeTests(RoomPageSetup):
    def setUp(self):
        super().setUp()
        self.allocation = RoomAllocation.objects.create(student=self.student, room=self.room)
        Room.objects.filter(pk=self.room.pk).update(occupied_count=1)
        self.client.force_login(self.admin)

    def test_moving_to_the_same_room_changes_nothing(self):
        response = self.client.post(
            reverse("rooms:move-student", args=[self.allocation.pk]), {"room_id": self.room.pk}
        )
        self.assertRedirects(response, reverse("rooms:allocation-list"))
        self.assertIn("The student already occupies this room.", message_texts(response))
        self.room.refresh_from_db()
        self.assertEqual(self.room.occupied_count, 1)

    def test_moving_to_a_full_room_is_rejected(self):
        full = Room.objects.create(
            block=self.block, room_number="201", floor=2, room_type=Room.RoomType.SINGLE,
            capacity=1, monthly_fee=2000, occupied_count=1,
        )
        response = self.client.post(
            reverse("rooms:move-student", args=[self.allocation.pk]), {"room_id": full.pk}
        )
        self.assertIn("The destination room is full.", message_texts(response))
        self.allocation.refresh_from_db()
        full.refresh_from_db()
        self.assertEqual(self.allocation.room_id, self.room.pk)
        self.assertEqual(full.occupied_count, 1)

    def test_allotting_an_application_that_is_not_pending_is_rejected(self):
        other = User.objects.create_user(
            srn="PES2UG24CS913", email="student913@example.com", password="Pass12345!",
        )
        application = RoomApplication.objects.create(
            student=other, status=RoomApplication.Status.REJECTED
        )
        response = self.client.post(
            reverse("rooms:allot-room", args=[application.pk]), {"room_id": self.room.pk}
        )
        self.assertRedirects(response, reverse("rooms:pending-applications"))
        self.assertIn("Application is not pending.", message_texts(response))
        self.assertFalse(RoomAllocation.objects.filter(student=other).exists())
