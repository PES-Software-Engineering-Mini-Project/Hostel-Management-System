"""NFR-2 performance guard rails: list pages stay constant-query as data grows.

Timed runs against seed data (`python manage.py seed_demo`) are recorded in the
pull request; these tests lock in the query behaviour that keeps pages fast.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from complaints.models import Complaint
from fees.models import FeeRecord, Payment


class PerformanceTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin_user = User.objects.create_user(
            srn="PES1UG23CS090", email="perf.admin@example.com", password="admin-password",
            first_name="Perf", last_name="Admin", contact_number="9876543200",
            role=User.Role.ADMIN,
        )
        cls.student = User.objects.create_user(
            srn="PES1UG23CS091", email="perf.student@example.com", password="student-password",
            first_name="Perf", last_name="Student", contact_number="9876543201",
        )
        students = [
            User(
                srn=f"PES1UG23CE{100 + i:03d}", email=f"perf{i}@example.com",
                first_name="Perf", last_name=f"Student{i}", contact_number="9876543300",
            )
            for i in range(60)
        ]
        for user in students:
            user.set_password("student-password")
        User.objects.bulk_create(students)
        students.append(cls.student)
        fee_records = [
            FeeRecord(student=user, term="2026-27 Odd Semester", amount_due="20000.00")
            for user in students
        ]
        FeeRecord.objects.bulk_create(fee_records)
        Payment.objects.bulk_create(
            [
                Payment(fee_record=record, amount="10000.00", recorded_by=cls.admin_user)
                for record in fee_records
            ]
        )
        Complaint.objects.bulk_create(
            [
                Complaint(student=user, category="other", description=f"Complaint {i}.")
                for i, user in enumerate(students)
            ]
        )


class ConstantQueryTests(PerformanceTestCase):
    def test_admin_fee_list_is_constant_query(self):
        self.client.force_login(self.admin_user)
        with self.assertNumQueries(3):
            response = self.client.get(reverse("fees:fee-list"))
        self.assertEqual(response.status_code, 200)

    def test_admin_complaint_list_is_constant_query(self):
        self.client.force_login(self.admin_user)
        with self.assertNumQueries(3):
            response = self.client.get(reverse("complaints:complaint-list"))
        self.assertEqual(response.status_code, 200)

    def test_my_fees_is_constant_query(self):
        self.client.force_login(self.student)
        with self.assertNumQueries(4):
            response = self.client.get(reverse("fees:my-fees"))
        self.assertEqual(response.status_code, 200)

    def test_my_complaints_is_constant_query(self):
        self.client.force_login(self.student)
        with self.assertNumQueries(3):
            response = self.client.get(reverse("complaints:my-complaints"))
        self.assertEqual(response.status_code, 200)
