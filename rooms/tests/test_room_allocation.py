from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.messages import get_messages
from django.db import close_old_connections, connection
from django.test import Client, TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse

from accounts.models import User
from rooms.models import Block, Room, RoomAllocation, RoomApplication


class RoomApplicationTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            srn="PES2UG24CS501",
            email="student501@example.com",
            password="TestPassword123!",
            role=User.Role.STUDENT,
        )
        self.admin = User.objects.create_user(
            srn="PES2UG24CS502",
            email="admin502@example.com",
            password="TestPassword123!",
            role=User.Role.ADMIN,
            is_staff=True,
        )
        self.block = Block.objects.create(
            name="Allocation Block",
            number_of_floors=3,
        )
        self.room = Room.objects.create(
            block=self.block,
            room_number="101",
            floor=1,
            room_type=Room.RoomType.DOUBLE,
            capacity=2,
            monthly_fee=1500,
            occupied_count=0,
        )

    def test_student_can_submit_room_application(self):
        self.client.force_login(self.student)

        response = self.client.post(
            reverse("rooms:apply"),
            {
                "preferred_block": self.block.pk,
                "preferred_room_type": Room.RoomType.DOUBLE,
            },
        )

        self.assertRedirects(response, reverse("student-dashboard"))
        self.assertTrue(
            RoomApplication.objects.filter(
                student=self.student,
                status=RoomApplication.Status.PENDING,
            ).exists()
        )

    def test_student_cannot_submit_duplicate_pending_application(self):
        RoomApplication.objects.create(student=self.student)
        self.client.force_login(self.student)

        response = self.client.post(
            reverse("rooms:apply"),
            {
                "preferred_block": self.block.pk,
                "preferred_room_type": Room.RoomType.DOUBLE,
            },
        )

        self.assertRedirects(response, reverse("student-dashboard"))
        self.assertEqual(
            RoomApplication.objects.filter(student=self.student).count(),
            1,
        )

    def test_student_cannot_access_pending_applications(self):
        self.client.force_login(self.student)

        response = self.client.get(
            reverse("rooms:pending-applications")
        )

        self.assertEqual(response.status_code, 403)


class RoomAllocationTests(RoomApplicationTests):
    def create_application(self, student=None):
        return RoomApplication.objects.create(
            student=student or self.student,
        )

    def test_admin_can_allot_vacant_room(self):
        application = self.create_application()
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("rooms:allot-room", args=[application.pk]),
            {"room_id": self.room.pk},
        )

        self.assertRedirects(
            response,
            reverse("rooms:pending-applications"),
        )
        self.assertTrue(
            RoomAllocation.objects.filter(
                student=self.student,
                room=self.room,
            ).exists()
        )

        self.room.refresh_from_db()
        application.refresh_from_db()

        self.assertEqual(self.room.occupied_count, 1)
        self.assertEqual(
            application.status,
            RoomApplication.Status.ALLOTTED,
        )

    def test_full_room_cannot_be_allotted(self):
        self.room.occupied_count = self.room.capacity
        self.room.save()
        application = self.create_application()
        self.client.force_login(self.admin)

        self.client.post(
            reverse("rooms:allot-room", args=[application.pk]),
            {"room_id": self.room.pk},
        )

        self.assertFalse(
            RoomAllocation.objects.filter(student=self.student).exists()
        )
        self.room.refresh_from_db()
        self.assertEqual(self.room.occupied_count, self.room.capacity)

    def test_student_cannot_receive_second_room(self):
        another_block = Block.objects.create(
            name="Second Block",
            number_of_floors=2,
        )
        another_room = Room.objects.create(
            block=another_block,
            room_number="201",
            floor=1,
            room_type=Room.RoomType.SINGLE,
            capacity=1,
            monthly_fee=1000,
            occupied_count=0,
        )

        RoomAllocation.objects.create(
            student=self.student,
            room=another_room,
        )
        another_application = self.create_application()
        self.client.force_login(self.admin)

        self.client.post(
            reverse("rooms:allot-room", args=[another_application.pk]),
            {"room_id": self.room.pk},
        )

        self.assertEqual(
            RoomAllocation.objects.filter(student=self.student).count(),
            1,
        )
        self.room.refresh_from_db()
        self.assertEqual(self.room.occupied_count, 0)

    def test_admin_can_deallocate_student(self):
        allocation = RoomAllocation.objects.create(
            student=self.student,
            room=self.room,
        )
        self.room.occupied_count = 1
        self.room.save()
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                "rooms:deallocate-student",
                args=[allocation.pk],
            )
        )

        self.assertRedirects(
            response,
            reverse("rooms:allocation-list"),
        )
        self.assertFalse(
            RoomAllocation.objects.filter(pk=allocation.pk).exists()
        )
        self.room.refresh_from_db()
        self.assertEqual(self.room.occupied_count, 0)
    def test_admin_can_move_student_to_another_room(self):
        allocation = RoomAllocation.objects.create(
            student=self.student,
            room=self.room,
        )
        self.room.occupied_count = 1
        self.room.save()

        destination = Room.objects.create(
            block=self.block,
            room_number="102",
            floor=1,
            room_type=Room.RoomType.DOUBLE,
            capacity=2,
            monthly_fee=1500,
            occupied_count=0,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                "rooms:move-student",
                args=[allocation.pk],
            ),
            {"room_id": destination.pk},
        )

        self.assertRedirects(
            response,
            reverse("rooms:allocation-list"),
        )

        allocation.refresh_from_db()
        self.room.refresh_from_db()
        destination.refresh_from_db()

        self.assertEqual(allocation.room_id, destination.pk)
        self.assertEqual(self.room.occupied_count, 0)
        self.assertEqual(destination.occupied_count, 1)

    def test_student_dashboard_displays_allocated_room(self):
        RoomAllocation.objects.create(
            student=self.student,
            room=self.room,
        )
        self.room.occupied_count = 1
        self.room.save()

        self.client.force_login(self.student)
        response = self.client.get(reverse("student-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "101")
        self.assertContains(response, "Allocation Block")

    def test_student_cannot_access_allocation_management(self):
        self.client.force_login(self.student)

        response = self.client.get(
            reverse("rooms:allocation-list")
        )

        self.assertEqual(response.status_code, 403)


# SQLite has no row locks and fails concurrent writes with "table is locked", so this
# runs on PostgreSQL only (the CI PostgreSQL step).
@skipUnlessDBFeature("has_select_for_update")
class ConcurrentRoomAllocationTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.admin = User.objects.create_user(
            srn="PES2UG24CS599",
            email="admin599@example.com",
            password="TestPassword123!",
            role=User.Role.ADMIN,
            is_staff=True,
        )

        self.block = Block.objects.create(
            name="Concurrency Block",
            number_of_floors=2,
        )

        self.room = Room.objects.create(
            block=self.block,
            room_number="301",
            floor=1,
            room_type=Room.RoomType.SINGLE,
            capacity=1,
            monthly_fee=1000,
            occupied_count=0,
        )

        self.students = [
            User.objects.create_user(
                srn=f"PES2UG24CS60{i}",
                email=f"student60{i}@example.com",
                password="TestPassword123!",
                role=User.Role.STUDENT,
            )
            for i in range(1, 3)
        ]

        self.applications = [
            RoomApplication.objects.create(student=student)
            for student in self.students
        ]

    def attempt_allotment(self, application_id, barrier):
        close_old_connections()

        try:
            client = Client()
            client.force_login(
                User.objects.get(pk=self.admin.pk)
            )

            barrier.wait(timeout=10)

            response = client.post(
                reverse(
                    "rooms:allot-room",
                    args=[application_id],
                ),
                {"room_id": self.room.pk},
            )

            response_messages = [
            str(message)
            for message in get_messages(response.wsgi_request)
        ]

            return response.status_code , response_messages

        finally:
            connection.close()

    def test_two_students_cannot_be_allotted_to_last_bed(self):
        barrier = Barrier(2)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    self.attempt_allotment,
                    application.pk,
                    barrier,
                )
                for application in self.applications
            ]

            results = [
                future.result(timeout=30)
                for future in futures
            ]

        for status_code, _ in results:
            self.assertEqual(status_code, 302)

        all_messages = [
            message
            for _, messages in results
            for message in messages
        ]

        self.assertEqual(
            all_messages.count("Room allotted successfully."),
            1,
        )

        self.assertEqual(
            all_messages.count("Room is full."),
            1,
        )

        self.room.refresh_from_db()

        self.assertEqual(
            RoomAllocation.objects.filter(room=self.room).count(),
            1,
        )

        self.assertEqual(self.room.occupied_count, 1)

        allotted_count = RoomApplication.objects.filter(
            status=RoomApplication.Status.ALLOTTED
        ).count()

        self.assertEqual(allotted_count, 1)

        pending_count = RoomApplication.objects.filter(
            status=RoomApplication.Status.PENDING
        ).count()

        self.assertEqual(pending_count, 1)
