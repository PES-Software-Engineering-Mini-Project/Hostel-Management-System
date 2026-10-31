"""FR-6.2: a new complaint is tagged with the student's allotted room (snapshot, set by the view)."""

from django.test import TestCase
from django.urls import reverse

from complaints.models import Complaint
from rooms.models import Block, Room, RoomAllocation

from .helpers import make_admin, make_complaint, make_user


class RoomTagTests(TestCase):
    def setUp(self):
        self.block = Block.objects.create(name="Block A", number_of_floors=3)
        self.room = self.make_room("101")
        self.student = make_user("PES1UG23CS801")
        self.admin_user = make_admin("PES1UG23AD801")

    def make_room(self, number):
        return Room.objects.create(
            block=self.block, room_number=number, floor=1,
            room_type=Room.RoomType.DOUBLE, capacity=2, monthly_fee="1000.00",
        )

    def post(self, student, **extra):
        self.client.force_login(student)
        data = {"category": "plumbing", "description": "Tap leaks.", **extra}
        return self.client.post(reverse("complaints:raise"), data)

    def test_room_comes_from_the_current_allocation(self):
        RoomAllocation.objects.create(student=self.student, room=self.room)
        self.post(self.student)
        self.assertEqual(Complaint.objects.get().room, self.room)

    def test_forged_room_in_the_post_is_ignored(self):
        RoomAllocation.objects.create(student=self.student, room=self.room)
        other = self.make_room("202")
        self.post(self.student, room=other.pk)
        self.assertEqual(Complaint.objects.get().room, self.room)

    def test_forged_room_ignored_for_student_with_no_room(self):
        self.post(self.student, room=self.room.pk)
        self.assertIsNone(Complaint.objects.get().room)

    def test_student_without_a_room_can_still_complain(self):
        response = self.post(self.student)
        self.assertRedirects(response, reverse("complaints:my-complaints"))
        complaint = Complaint.objects.get()
        self.assertIsNone(complaint.room)
        self.assertEqual(complaint.status, Complaint.Status.OPEN)

    def test_room_is_a_snapshot_after_the_student_moves(self):
        allocation = RoomAllocation.objects.create(student=self.student, room=self.room)
        self.post(self.student)
        allocation.room = self.make_room("303")
        allocation.save()
        self.assertEqual(Complaint.objects.get().room, self.room)

    def test_deleting_an_empty_room_keeps_the_complaint_with_room_empty(self):
        complaint = make_complaint(self.student, room=self.room)
        self.room.delete()  # empty room, so allowed (FR-3.5)
        complaint.refresh_from_db()
        self.assertIsNone(complaint.room)

    def test_admin_list_student_list_and_detail_show_block_and_room(self):
        complaint = make_complaint(self.student, room=self.room)
        self.client.force_login(self.admin_user)
        self.assertContains(self.client.get(reverse("complaints:complaint-list")), "Block A - Room 101")
        self.client.force_login(self.student)
        self.assertContains(self.client.get(reverse("complaints:my-complaints")), "Block A - Room 101")
        self.assertContains(
            self.client.get(reverse("complaints:detail", args=[complaint.pk])), "Block A - Room 101"
        )

    def test_no_room_shows_a_dash_not_none(self):
        make_complaint(self.student)
        self.client.force_login(self.admin_user)
        self.assertNotContains(self.client.get(reverse("complaints:complaint-list")), "None")
