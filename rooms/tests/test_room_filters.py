"""Room filters on the admin room list (FR-9.2, FR-9.4)."""

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from rooms.models import Block, Room


class RoomFilterTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            srn="PES2UG24CS801",
            email="filter-admin@example.com",
            password="TestPassword123!",
            role=User.Role.ADMIN,
        )
        self.block_a = Block.objects.create(name="A Block", number_of_floors=3)
        self.block_b = Block.objects.create(name="B Block", number_of_floors=3)
        self.empty_single = self.make_room(self.block_a, "101", 1, Room.RoomType.SINGLE, 1, 0)
        self.half_double = self.make_room(self.block_a, "201", 2, Room.RoomType.DOUBLE, 2, 1)
        self.full_triple = self.make_room(self.block_b, "101", 1, Room.RoomType.TRIPLE, 3, 3)
        self.client.force_login(self.admin_user)
        self.url = reverse("rooms:room-list")

    def make_room(self, block, number, floor, room_type, capacity, occupied):
        return Room.objects.create(
            block=block,
            room_number=number,
            floor=floor,
            room_type=room_type,
            capacity=capacity,
            monthly_fee=5000,
            occupied_count=occupied,
        )

    def rooms_for(self, **params):
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 200)
        return set(response.context["rooms"])

    def test_filter_by_block(self):
        self.assertEqual(
            self.rooms_for(block=self.block_a.pk), {self.empty_single, self.half_double}
        )

    def test_filter_by_floor(self):
        self.assertEqual(self.rooms_for(floor=1), {self.empty_single, self.full_triple})

    def test_filter_by_type(self):
        self.assertEqual(self.rooms_for(room_type=Room.RoomType.DOUBLE), {self.half_double})

    def test_filter_by_status(self):
        self.assertEqual(
            self.rooms_for(status="available"), {self.empty_single, self.half_double}
        )
        self.assertEqual(self.rooms_for(status="full"), {self.full_triple})
        self.assertEqual(self.rooms_for(status="empty"), {self.empty_single})

    def test_filters_combine(self):
        self.assertEqual(self.rooms_for(block=self.block_a.pk, floor=1), {self.empty_single})

    def test_no_matches_shows_message_not_error(self):
        response = self.client.get(self.url, {"block": self.block_b.pk, "status": "empty"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No results found")

    def test_bad_input_is_ignored_with_field_errors(self):
        response = self.client.get(
            self.url, {"floor": "abc", "status": "haunted", "block": "999", "room_type": "Suite"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["rooms"]), 3)
        self.assertTrue(response.context["filter_form"].errors)

    def test_room_list_shows_status_column(self):
        response = self.client.get(self.url)

        self.assertContains(response, "Has a free bed")
        self.assertContains(response, "Full")
        self.assertContains(response, "Empty")

    def test_room_list_is_a_single_html_document(self):
        response = self.client.get(self.url)

        self.assertEqual(response.content.decode().lower().count("<html"), 1)

    def test_student_cannot_filter_rooms(self):
        student = User.objects.create_user(
            srn="PES2UG24CS802",
            email="filter-student@example.com",
            password="TestPassword123!",
            role=User.Role.STUDENT,
        )
        self.client.force_login(student)

        self.assertEqual(self.client.get(self.url, {"status": "full"}).status_code, 403)
