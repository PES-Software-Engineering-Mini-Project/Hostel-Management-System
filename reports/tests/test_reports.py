"""Unit tests for the report builders (SRS §3.1 Reports screen, issue #19)."""

from decimal import Decimal

from django.test import TestCase

from complaints.models import Complaint
from reports.reports import complaint_report, fee_due_report, occupancy_report

from .helpers import make_admin, make_block, make_complaint, make_fee, make_room, make_user


class OccupancyReportTests(TestCase):
    def test_empty_when_no_rooms(self):
        data = occupancy_report()
        self.assertTrue(data.is_empty)
        self.assertEqual(data.totals, [])

    def test_groups_rooms_by_block_and_floor(self):
        a = make_block("A Block")
        b = make_block("B Block")
        make_room(a, "101", floor=1, room_type="Double", occupied=2)
        make_room(a, "102", floor=1, room_type="Triple", occupied=1)
        make_room(a, "201", floor=2, room_type="Single", occupied=0)
        make_room(b, "101", floor=1, room_type="Single", occupied=1)

        data = occupancy_report()

        self.assertEqual(
            data.rows,
            [
                ["A Block", 1, 2, 5, 3, 2, Decimal("60.0")],
                ["A Block", 2, 1, 1, 0, 1, Decimal("0.0")],
                ["B Block", 1, 1, 1, 1, 0, Decimal("100.0")],
            ],
        )
        self.assertEqual(data.totals, ["All blocks", "", 4, 7, 4, 3, Decimal("57.1")])

    def test_runs_one_query_however_many_rooms(self):
        block = make_block()
        for number in range(30):
            make_room(block, f"{100 + number}", floor=1 + number % 3)
        with self.assertNumQueries(1):
            occupancy_report()


class FeeDueReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_admin()

    def test_empty_when_everything_is_paid(self):
        student = make_user("PES1UG23CS001")
        make_fee(student, "1000.00", paid=["1000.00"], recorded_by=self.admin)
        self.assertTrue(fee_due_report().is_empty)

    def test_lists_only_records_with_a_balance(self):
        block = make_block()
        room = make_room(block, "101", occupied=1)
        owing = make_user("PES1UG23CS002", first_name="Asha", last_name="Rao")
        partly = make_user("PES1UG23CS001", first_name="Ben", last_name="Das")
        paid_up = make_user("PES1UG23CS003")
        make_fee(owing, "30000.00", room=room)
        make_fee(partly, "20000.00", paid=["5000.00", "2500.00"], recorded_by=self.admin)
        make_fee(paid_up, "10000.00", paid=["10000.00"], recorded_by=self.admin)

        data = fee_due_report()

        self.assertEqual(
            data.rows,
            [
                ["PES1UG23CS001", "Ben Das", "", "2026-27 Odd", Decimal("20000.00"),
                 Decimal("7500.00"), Decimal("12500.00")],
                ["PES1UG23CS002", "Asha Rao", "A Block 101", "2026-27 Odd", Decimal("30000.00"),
                 Decimal("0.00"), Decimal("30000.00")],
            ],
        )
        self.assertEqual(data.totals[0], "2 students")
        self.assertEqual(data.totals[-1], Decimal("42500.00"))

    def test_one_row_per_term_owed(self):
        student = make_user("PES1UG23CS004")
        make_fee(student, "1000.00", term="2026-27 Odd")
        make_fee(student, "2000.00", term="2026-27 Even")
        data = fee_due_report()
        self.assertEqual([row[3] for row in data.rows], ["2026-27 Even", "2026-27 Odd"])
        self.assertEqual(data.totals[0], "1 students")

    def test_query_count_does_not_grow_with_records(self):
        for i in range(20):
            make_fee(make_user(f"PES1UG23CS{100 + i}"), "1000.00", paid=["10.00"],
                     recorded_by=self.admin)
        with self.assertNumQueries(1):
            fee_due_report()


class ComplaintReportTests(TestCase):
    def test_empty_when_no_complaints(self):
        self.assertTrue(complaint_report().is_empty)

    def test_counts_by_category_and_status(self):
        student = make_user("PES1UG23CS001")
        make_complaint(student, "plumbing", Complaint.Status.OPEN)
        make_complaint(student, "plumbing", Complaint.Status.OPEN)
        make_complaint(student, "plumbing", Complaint.Status.RESOLVED)
        make_complaint(student, "internet", Complaint.Status.IN_PROGRESS)

        data = complaint_report()

        self.assertEqual(data.headers, ["Category", "Open", "In Progress", "Resolved", "Total"])
        rows = {row[0]: row[1:] for row in data.rows}
        self.assertEqual(rows["Plumbing"], [2, 0, 1, 3])
        self.assertEqual(rows["Internet"], [0, 1, 0, 1])
        self.assertEqual(rows["Electrical"], [0, 0, 0, 0])
        self.assertEqual(len(data.rows), len(Complaint.Category.choices))
        self.assertEqual(data.totals, ["All categories", 2, 1, 1, 4])
