"""NFR-5 scalability: the system works with about 1000 students and 500 rooms.

The data comes from the same ``seed_demo`` command used for manual checks, at the NFR-5
scale. Every list page must be paginated, stay within the SAD §3.7 limit of 20 queries
and answer within the NFR-2 two-second budget, and the filtered columns must be indexed.
"""

import time
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from complaints.models import Complaint
from fees.models import FeeRecord
from rooms.models import Room, RoomAllocation, RoomApplication

STUDENTS = 1000
BLOCKS = 5
ROOMS_PER_BLOCK = 100
QUERY_LIMIT = 20  # SAD §3.7
TIME_LIMIT_SECONDS = 2  # NFR-2


class ScaleTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin_user = User.objects.create_user(
            srn="PES1UG23AD900", email="scale.admin@example.com", password="admin-password",
            first_name="Scale", last_name="Admin", contact_number="9876543200",
            role=User.Role.ADMIN,
        )
        call_command(
            "seed_demo",
            blocks=BLOCKS,
            rooms_per_block=ROOMS_PER_BLOCK,
            students=STUDENTS,
            complaints=300,
            stdout=StringIO(),
        )
        students = list(User.objects.filter(role=User.Role.STUDENT).order_by("srn"))
        rooms = list(Room.objects.order_by("pk"))
        RoomAllocation.objects.bulk_create(
            RoomAllocation(student=student, room=room)
            for student, room in zip(students[:100], rooms)
        )
        Room.objects.filter(pk__in=[room.pk for room in rooms[:100]]).update(occupied_count=1)
        RoomApplication.objects.bulk_create(
            RoomApplication(student=student) for student in students[100:160]
        )
        cls.busy_student = students[200]
        Complaint.objects.bulk_create(
            Complaint(student=cls.busy_student, category="other", description=f"Issue {i}.")
            for i in range(40)
        )

    def timed_get(self, url):
        with CaptureQueriesContext(connection) as queries:
            start = time.perf_counter()
            response = self.client.get(url)
            elapsed = time.perf_counter() - start
        return response, len(queries), elapsed


class SeedScaleTests(ScaleTestCase):
    def test_seed_reaches_the_nfr5_scale(self):
        User = get_user_model()
        self.assertGreaterEqual(User.objects.filter(role=User.Role.STUDENT).count(), STUDENTS)
        self.assertEqual(Room.objects.count(), BLOCKS * ROOMS_PER_BLOCK)
        self.assertEqual(FeeRecord.objects.count(), STUDENTS)

    def test_seeded_srns_fit_the_column_and_are_unique(self):
        srns = list(get_user_model().objects.values_list("srn", flat=True))
        self.assertEqual(len(srns), len(set(srns)))
        self.assertLessEqual(max(len(srn) for srn in srns), 13)

    def test_seeded_rooms_are_on_floors_their_block_has(self):
        for room in Room.objects.select_related("block").order_by("-floor")[:5]:
            room.full_clean()


class PaginatedListTests(ScaleTestCase):
    def admin_list_urls(self):
        return [
            reverse("student-list"),
            reverse("rooms:room-list"),
            reverse("rooms:pending-applications"),
            reverse("rooms:allocation-list"),
            reverse("fees:fee-list"),
            reverse("complaints:complaint-list"),
        ]

    def test_admin_lists_are_paginated_within_query_and_time_limits(self):
        self.client.force_login(self.admin_user)
        for url in self.admin_list_urls():
            with self.subTest(url=url):
                response, query_count, elapsed = self.timed_get(url)
                self.assertEqual(response.status_code, 200)
                page = response.context["page_obj"]
                self.assertEqual(len(page.object_list), settings.HMS_PAGE_SIZE)
                self.assertGreater(page.paginator.num_pages, 1)
                self.assertContains(response, f"Page 1 of {page.paginator.num_pages}")
                self.assertLessEqual(query_count, QUERY_LIMIT)
                self.assertLess(elapsed, TIME_LIMIT_SECONDS)

    def test_admin_dashboard_stays_within_limits(self):
        self.client.force_login(self.admin_user)
        response, query_count, elapsed = self.timed_get(reverse("admin-dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(query_count, QUERY_LIMIT)
        self.assertLess(elapsed, TIME_LIMIT_SECONDS)

    def test_student_complaint_list_is_paginated(self):
        self.client.force_login(self.busy_student)
        response, query_count, _ = self.timed_get(reverse("complaints:my-complaints"))
        page = response.context["page_obj"]
        self.assertEqual(len(page.object_list), settings.HMS_PAGE_SIZE)
        self.assertTrue(all(c.student_id == self.busy_student.pk for c in page.object_list))
        self.assertLessEqual(query_count, QUERY_LIMIT)

    def test_pages_do_not_repeat_or_skip_rows(self):
        self.client.force_login(self.admin_user)
        seen = []
        page_number = 1
        while True:
            response = self.client.get(reverse("fees:fee-list"), {"page": page_number})
            page = response.context["page_obj"]
            seen += [record.pk for record in page.object_list]
            if not page.has_next():
                break
            page_number += 1
        self.assertEqual(len(seen), FeeRecord.objects.count())
        self.assertEqual(len(set(seen)), len(seen))

    def test_page_links_keep_the_active_filters(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("rooms:room-list"), {"room_type": "Triple"})
        page = response.context["page_obj"]
        self.assertTrue(all(room.room_type == "Triple" for room in page.object_list))
        self.assertContains(response, "?room_type=Triple&amp;page=2")

        second = self.client.get(reverse("rooms:room-list"), {"room_type": "Triple", "page": 2})
        self.assertEqual(second.context["page_obj"].number, 2)
        self.assertTrue(
            all(room.room_type == "Triple" for room in second.context["page_obj"].object_list)
        )

    def test_bad_page_numbers_fall_back_instead_of_erroring(self):
        self.client.force_login(self.admin_user)
        url = reverse("student-list")
        last = self.client.get(url, {"page": 99999}).context["page_obj"]
        self.assertEqual(last.number, last.paginator.num_pages)
        for bad in ["abc", "-1", "0", ""]:
            with self.subTest(page=bad):
                response = self.client.get(url, {"page": bad})
                self.assertEqual(response.status_code, 200)

    def test_search_results_are_paginated_too(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("student-list"), {"q": "PES1UG23CS"})
        page = response.context["page_obj"]
        self.assertEqual(len(page.object_list), settings.HMS_PAGE_SIZE)
        self.assertContains(response, "?q=PES1UG23CS&amp;page=2")


class IndexTests(TestCase):
    """SAD §3.6: indexes on the columns list pages filter by."""

    INDEXED = [
        (get_user_model(), ["srn"]),
        (get_user_model(), ["role"]),
        (Room, ["block_id"]),
        (Room, ["floor"]),
        (Room, ["room_type"]),
        (RoomApplication, ["status"]),
        (Complaint, ["status"]),
        (Complaint, ["category"]),
        (FeeRecord, ["student_id"]),
    ]

    def test_filtered_columns_are_indexed(self):
        with connection.cursor() as cursor:
            for model, columns in self.INDEXED:
                with self.subTest(table=model._meta.db_table, columns=columns):
                    constraints = connection.introspection.get_constraints(
                        cursor, model._meta.db_table
                    )
                    leading = [
                        c["columns"][: len(columns)]
                        for c in constraints.values()
                        if c["index"] or c["unique"] or c["primary_key"]
                    ]
                    self.assertIn(columns, leading)
