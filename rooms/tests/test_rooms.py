
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.db import IntegrityError, transaction
from rooms.models import Block, Room
from django.urls import reverse
from django.test import TestCase
from accounts.models import User

class RoomDeletionTests(TestCase):
    def setUp(self):
        self.block = Block.objects.create(
            name="Test Block",
            number_of_floors=4,
        )
        self.room = Room.objects.create(
            block=self.block,
            room_number="TEST-101",
            floor=1,
            room_type=Room.RoomType.SINGLE,
            capacity=1,
            monthly_fee=1000,
            occupied_count=1,
        )

    def test_occupied_room_cannot_be_deleted(self):
        with self.assertRaises(ValidationError):
            self.room.delete()

        self.assertTrue(
            Room.objects.filter(pk=self.room.pk).exists()
        )

    def test_unoccupied_room_can_be_deleted(self):
        self.room.occupied_count = 0
        self.room.save()

        self.room.delete()

        self.assertFalse(
            Room.objects.filter(pk=self.room.pk).exists()
        )


class RoomValidationTests(TestCase):
    def setUp(self):
        self.block = Block.objects.create(
            name="Validation Block",
            number_of_floors=3,
        )

    def make_room(self, **overrides):
        data = {
            "block": self.block,
            "room_number": "101",
            "floor": 1,
            "room_type": Room.RoomType.SINGLE,
            "capacity": 1,
            "monthly_fee": 1000,
            "occupied_count": 0,
        }
        data.update(overrides)
        return Room(**data)

    def test_valid_room_passes_validation(self):
        self.make_room().full_clean()

    def test_floor_cannot_exceed_block_floors(self):
        room = self.make_room(floor=4)

        with self.assertRaises(ValidationError):
            room.full_clean()

    def test_single_room_requires_capacity_one(self):
        room = self.make_room(capacity=2)

        with self.assertRaises(ValidationError):
            room.full_clean()

    def test_occupied_count_cannot_exceed_capacity(self):
        room = self.make_room(occupied_count=2)

        with self.assertRaises(ValidationError):
            room.full_clean()

    def test_negative_monthly_fee_is_rejected(self):
        room = self.make_room(monthly_fee=-100)

        with self.assertRaises(ValidationError):
            room.full_clean()

    def test_blank_floor_does_not_raise_type_error(self):
        room = self.make_room(floor=None)

        with self.assertRaises(ValidationError) as context:
            room.full_clean()

        self.assertIn("floor", context.exception.message_dict)

class RoomUniquenessTests(TestCase):
    def setUp(self):
        self.block_a = Block.objects.create(
            name="Block A",
            number_of_floors=3,
        )
        self.block_b = Block.objects.create(
            name="Block B",
            number_of_floors=3,
        )

    def create_room(self, block, room_number):
        return Room.objects.create(
            block=block,
            room_number=room_number,
            floor=1,
            room_type=Room.RoomType.SINGLE,
            capacity=1,
            monthly_fee=1000,
            occupied_count=0,
        )

    def test_duplicate_room_number_in_same_block_is_rejected(self):
        self.create_room(self.block_a, "101")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_room(self.block_a, "101")

    def test_same_room_number_in_different_blocks_is_allowed(self):
        self.create_room(self.block_a, "101")
        self.create_room(self.block_b, "101")

        self.assertEqual(Room.objects.filter(room_number="101").count(), 2)


class QuerysetDeletionTests(TestCase):
    def setUp(self):
        self.block = Block.objects.create(
            name="Deletion Block",
            number_of_floors=3,
        )
        self.room = Room.objects.create(
            block=self.block,
            room_number="201",
            floor=2,
            room_type=Room.RoomType.DOUBLE,
            capacity=2,
            monthly_fee=1500,
            occupied_count=1,
        )

    def test_queryset_cannot_delete_occupied_room(self):
        with self.assertRaises(ValidationError):
            Room.objects.filter(pk=self.room.pk).delete()

        self.assertTrue(
            Room.objects.filter(pk=self.room.pk).exists()
        )

    def test_queryset_can_delete_unoccupied_room(self):
        self.room.occupied_count = 0
        self.room.save()

        Room.objects.filter(pk=self.room.pk).delete()

        self.assertFalse(
            Room.objects.filter(pk=self.room.pk).exists()
        )


class AdditionalValidationTests(TestCase):
    def setUp(self):
        self.block = Block.objects.create(
            name="Additional Validation Block",
            number_of_floors=3,
        )

    def make_room(self, **overrides):
        data = {
            "block": self.block,
            "room_number": "301",
            "floor": 1,
            "room_type": Room.RoomType.SINGLE,
            "capacity": 1,
            "monthly_fee": 1000,
            "occupied_count": 0,
        }
        data.update(overrides)
        return Room(**data)

    def test_blank_capacity_returns_validation_error(self):
        room = self.make_room(capacity=None)

        with self.assertRaises(ValidationError) as context:
            room.full_clean()

        self.assertIn("capacity", context.exception.message_dict)

    def test_blank_occupied_count_returns_validation_error(self):
        room = self.make_room(occupied_count=None)

        with self.assertRaises(ValidationError) as context:
            room.full_clean()

        self.assertIn(
            "occupied_count",
            context.exception.message_dict,
        )

    def test_block_floors_cannot_be_reduced_below_room_floor(self):
        Room.objects.create(
            block=self.block,
            room_number="303",
            floor=3,
            room_type=Room.RoomType.SINGLE,
            capacity=1,
            monthly_fee=1000,
            occupied_count=0,
        )

        self.block.number_of_floors = 2

        with self.assertRaises(ValidationError) as context:
            self.block.full_clean()

        self.assertIn(
            "number_of_floors",
            context.exception.message_dict,
        )


class RoomAccessControlTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            srn="PES2UG24CS001",
            email="admin@example.com",
            password="TestPassword123!",
            role=User.Role.ADMIN,
        )
        self.student_user = User.objects.create_user(
            srn="PES2UG24CS002",
            email="student@example.com",
            password="TestPassword123!",
            role=User.Role.STUDENT,
        )

    def test_admin_can_access_room_list(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("rooms:room-list"))

        self.assertEqual(response.status_code, 200)

    def test_student_gets_forbidden_for_room_list(self):
        self.client.force_login(self.student_user)

        response = self.client.get(reverse("rooms:room-list"))

        self.assertEqual(response.status_code, 403)

    def test_student_cannot_access_add_block_page(self):
        self.client.force_login(self.student_user)

        response = self.client.get(reverse("rooms:block-create"))

        self.assertEqual(response.status_code, 403)

    def test_student_cannot_access_add_room_page(self):
        self.client.force_login(self.student_user)

        response = self.client.get(reverse("rooms:room-create"))

        self.assertEqual(response.status_code, 403)

    def test_admin_can_access_add_block_page(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("rooms:block-create"))

        self.assertEqual(response.status_code, 200)

    def test_admin_can_access_add_room_page(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("rooms:room-create"))

        self.assertEqual(response.status_code, 200)

class RoomAdminDeletionTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            srn="PES2UG24CS099",
            email="roomadmin@example.com",
            password="TestPassword123!",
            role=User.Role.ADMIN,
            is_staff=True,
        )
        self.block = Block.objects.create(
            name="Admin Test Block",
            number_of_floors=3,
        )
        self.room = Room.objects.create(
            block=self.block,
            room_number="901",
            floor=1,
            room_type=Room.RoomType.SINGLE,
            capacity=1,
            monthly_fee=1000,
            occupied_count=1,
        )
        self.client.force_login(self.admin_user)

    def test_admin_cannot_delete_occupied_room(self):
        url = reverse(
            "admin:rooms_room_delete",
            args=[self.room.pk],
        )

        response = self.client.post(url, {"post": "yes"})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Room.objects.filter(pk=self.room.pk).exists()
        )
