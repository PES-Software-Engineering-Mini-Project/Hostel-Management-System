"""Complaint room tagging (FR-6.2, issue #49)."""

from django.test import TestCase
from django.urls import reverse

from complaints.models import Complaint
from rooms.models import Room, RoomAllocation

from .helpers import allot_room, make_admin, make_complaint, make_user


class ComplaintRoomTagTests(TestCase):
    def setUp(self):
        self.admin_user = make_admin()
        self.student = make_user("PES1UG23CS711", first_name="Asha")
        self.room = allot_room(self.student)

    def raise_complaint(self, client, **extra):
        data = {"category": "plumbing", "description": "Tap is leaking."}
        data.update(extra)
        return client.post(reverse("complaints:raise"), data)

    def test_allotted_students_complaint_stores_their_current_room(self):
        self.client.force_login(self.student)

        self.raise_complaint(self.client)

        complaint = Complaint.objects.get(description="Tap is leaking.")
        self.assertEqual(complaint.room, self.room)

    def test_room_posted_in_the_form_is_ignored(self):  # NFR-3
        other_student = make_user("PES1UG23CS712")
        other_room = allot_room(other_student, room_number="102")
        self.client.force_login(self.student)

        self.raise_complaint(self.client, room=other_room.pk)

        complaint = Complaint.objects.get(description="Tap is leaking.")
        self.assertEqual(complaint.room, self.room)

    def test_student_without_a_room_raises_a_complaint_with_no_room(self):
        self.client.force_login(make_user("PES1UG23CS713"))

        response = self.raise_complaint(self.client)

        self.assertEqual(response.status_code, 302)
        complaint = Complaint.objects.get(description="Tap is leaking.")
        self.assertIsNone(complaint.room)

    def test_room_is_kept_when_the_student_moves_later(self):
        self.client.force_login(self.student)
        self.raise_complaint(self.client)
        complaint = Complaint.objects.get(description="Tap is leaking.")

        # Admin moves the student to another room after the complaint was raised.
        new_room = allot_room(make_user("PES1UG23CS714"), room_number="201")
        allocation = RoomAllocation.objects.get(student=self.student)
        allocation.room = new_room
        allocation.save()

        complaint.refresh_from_db()
        self.assertEqual(complaint.room, self.room)

    def test_admin_list_and_student_detail_show_block_and_room_number(self):
        complaint = make_complaint(self.student, room=self.room)

        admin_client = self.client
        admin_client.force_login(self.admin_user)
        list_response = admin_client.get(reverse("complaints:complaint-list"))

        self.assertContains(list_response, "A Block")
        self.assertContains(list_response, "Room 101")

        self.client.force_login(self.student)
        detail_response = self.client.get(reverse("complaints:detail", args=[complaint.pk]))

        self.assertContains(detail_response, "A Block - Room 101")

    def test_complaint_without_a_room_shows_a_placeholder(self):
        complaint = make_complaint(self.student)  # no room
        self.client.force_login(self.admin_user)

        list_response = self.client.get(reverse("complaints:complaint-list"))

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "<td>-</td>", html=True)

        self.client.force_login(self.student)
        detail_response = self.client.get(reverse("complaints:detail", args=[complaint.pk]))

        self.assertContains(detail_response, "Not allotted")
