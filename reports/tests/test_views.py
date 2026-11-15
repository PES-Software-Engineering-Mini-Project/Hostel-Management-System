"""Integration tests for the Reports screen and CSV downloads (issue #19)."""

import csv
import io
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from complaints.models import Complaint
from fees.models import FeeRecord
from reports.reports import REPORTS
from rooms.models import Room

from .helpers import make_admin, make_block, make_complaint, make_fee, make_room, make_user

SLUGS = list(REPORTS)


def read_csv(response):
    text = response.content.decode("utf-8")
    assert text.startswith("﻿"), "CSV should start with a byte-order mark for Excel"
    return list(csv.reader(io.StringIO(text[1:])))


class ReportsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_admin()
        cls.student = make_user("PES1UG23CS050", first_name="Asha", last_name="Rao")

    def setUp(self):
        self.client.force_login(self.admin)

    def all_report_urls(self):
        urls = [reverse("reports:index")]
        for slug in SLUGS:
            urls += [reverse("reports:detail", args=[slug]), reverse("reports:csv", args=[slug])]
        return urls


class AccessTests(ReportsTestCase):
    def test_students_get_403(self):
        self.client.force_login(self.student)
        for url in self.all_report_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_anonymous_users_are_sent_to_login(self):
        self.client.logout()
        for url in self.all_report_urls():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("login"), response["Location"])

    def test_unknown_report_is_404(self):
        self.assertEqual(self.client.get("/reports/visitors-ever/").status_code, 404)
        self.assertEqual(self.client.get("/reports/visitors-ever/csv/").status_code, 404)

    def test_admin_nav_links_to_reports(self):
        response = self.client.get(reverse("admin-dashboard"))
        self.assertContains(response, f'href="{reverse("reports:index")}"')

    def test_student_nav_has_no_reports_link(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student-dashboard"))
        self.assertNotContains(response, reverse("reports:index"))


class EmptyReportTests(ReportsTestCase):
    def test_each_empty_report_shows_a_message_not_an_error(self):
        for slug, report in REPORTS.items():
            with self.subTest(report=slug):
                response = self.client.get(reverse("reports:detail", args=[slug]))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, report.empty_message)
                self.assertNotContains(response, "<table")
                self.assertNotContains(response, reverse("reports:csv", args=[slug]))

    def test_empty_csv_downloads_with_the_message(self):
        for slug, report in REPORTS.items():
            with self.subTest(report=slug):
                response = self.client.get(reverse("reports:csv", args=[slug]))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(read_csv(response), [[report.empty_message]])


class IndexTests(ReportsTestCase):
    def test_lists_every_report_with_view_and_csv_links(self):
        response = self.client.get(reverse("reports:index"))
        self.assertEqual(response.status_code, 200)
        for slug, report in REPORTS.items():
            self.assertContains(response, report.title)
            self.assertContains(response, reverse("reports:detail", args=[slug]))
            self.assertContains(response, reverse("reports:csv", args=[slug]))


class CsvDownloadTests(ReportsTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        block = make_block("A Block")
        cls.room = make_room(block, "101", room_type=Room.RoomType.TRIPLE, occupied=2)
        make_room(block, "201", floor=2, room_type=Room.RoomType.SINGLE)
        make_fee(cls.student, "30000.00", paid=["10000.00"], recorded_by=cls.admin, room=cls.room)
        make_complaint(cls.student, "electrical")
        make_complaint(cls.student, "electrical", Complaint.Status.RESOLVED)

    def test_csv_is_an_attachment_with_a_dated_name(self):
        response = self.client.get(reverse("reports:csv", args=["occupancy"]))
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertRegex(
            response["Content-Disposition"],
            r'^attachment; filename="hms-occupancy-report-\d{4}-\d{2}-\d{2}\.csv"$',
        )

    def test_occupancy_csv_rows_match_the_database(self):
        rows = read_csv(self.client.get(reverse("reports:csv", args=["occupancy"])))
        self.assertEqual(rows[0][:2], ["Block", "Floor"])
        body = rows[1:]
        self.assertEqual(len(body), 2)
        for row in body:
            rooms = Room.objects.filter(block__name=row[0], floor=int(row[1]))
            self.assertEqual(int(row[2]), rooms.count())
            self.assertEqual(int(row[3]), sum(r.capacity for r in rooms))
            self.assertEqual(int(row[4]), sum(r.occupied_count for r in rooms))

    def test_fee_due_csv_rows_match_the_database(self):
        rows = read_csv(self.client.get(reverse("reports:csv", args=["fee-dues"])))
        record = FeeRecord.objects.get(student=self.student)
        self.assertEqual(
            rows,
            [
                ["SRN", "Student", "Room", "Term", "Amount due", "Paid", "Balance"],
                ["PES1UG23CS050", "Asha Rao", "A Block 101", "2026-27 Odd", "30000.00",
                 "10000.00", str(record.balance)],
            ],
        )

    def test_complaint_csv_rows_match_the_database(self):
        rows = read_csv(self.client.get(reverse("reports:csv", args=["complaints"])))
        electrical = next(row for row in rows if row[0] == "Electrical")
        self.assertEqual(electrical, ["Electrical", "1", "0", "1", "2"])
        self.assertEqual(sum(int(row[-1]) for row in rows[1:]), Complaint.objects.count())

    def test_html_page_shows_the_same_rows_and_totals(self):
        response = self.client.get(reverse("reports:detail", args=["fee-dues"]))
        self.assertContains(response, "PES1UG23CS050")
        self.assertContains(response, "20000.00")
        self.assertContains(response, "1 student<")
        self.assertContains(response, reverse("reports:csv", args=["fee-dues"]))

    def test_blank_room_shows_a_dash_on_screen_and_blank_in_csv(self):
        other = make_user("PES1UG23CS051")
        make_fee(other, "500.00", term="2026-27 Even")
        response = self.client.get(reverse("reports:detail", args=["fee-dues"]))
        self.assertContains(response, "—")
        rows = read_csv(self.client.get(reverse("reports:csv", args=["fee-dues"])))
        self.assertEqual(rows[2][2], "")


class CsvInjectionTests(ReportsTestCase):
    def test_formula_like_names_are_neutralised(self):
        student = make_user("PES1UG23CS052", first_name="=HYPERLINK(\"x\")", last_name="Evil")
        make_fee(student, "100.00")
        rows = read_csv(self.client.get(reverse("reports:csv", args=["fee-dues"])))
        self.assertEqual(rows[1][1], "'=HYPERLINK(\"x\") Evil")

    def test_numbers_are_left_alone(self):
        make_fee(make_user("PES1UG23CS053"), "100.00")
        rows = read_csv(self.client.get(reverse("reports:csv", args=["fee-dues"])))
        self.assertEqual(rows[1][-1], "100.00")


class QueryCountTests(ReportsTestCase):
    """SAD §3.7: a page stays within a fixed number of queries as data grows."""

    def test_report_pages_do_not_grow_with_data(self):
        block = make_block("B Block")
        for i in range(15):
            student = make_user(f"PES1UG23CS{200 + i}")
            room = make_room(block, f"{100 + i}", floor=1 + i % 3, occupied=1)
            make_fee(student, "1000.00", paid=["1.00"], recorded_by=self.admin, room=room,
                     term=f"Term {i}")
            make_complaint(student)
        for slug in SLUGS:
            with self.subTest(report=slug):
                # session + user + the report's own query
                with self.assertNumQueries(3):
                    self.client.get(reverse("reports:detail", args=[slug]))
                with self.assertNumQueries(3):
                    self.client.get(reverse("reports:csv", args=[slug]))

    def test_fee_due_totals_are_decimals(self):
        make_fee(self.student, "10.10", paid=["0.05"], recorded_by=self.admin)
        response = self.client.get(reverse("reports:detail", args=["fee-dues"]))
        self.assertEqual(response.context["data"].totals[-1], Decimal("10.05"))
