"""Seed a small, hand-made data set that shows every functional requirement in a demo.

Unlike ``seed_demo`` (bulk data for performance checks) every row here is there for a
reason; run ``python manage.py seed_story`` and see the printed demo script.
Safe to re-run: if the demo admin already exists nothing is changed.
"""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from complaints.models import Complaint
from fees.models import FeeRecord, Payment
from rooms.models import Block, Room, RoomAllocation, RoomApplication
from visitors.models import Visitor

TERM = "2026-27 Odd Semester"
ADMIN_SRN = "DEMOADMIN01"

# (srn, first, last, branch, year)
STUDENTS = [
    ("PES1UG24CS001", "Aarav", "Sharma", "CSE", 2),  # single room, fully paid
    ("PES1UG24CS002", "Diya", "Rao", "ECE", 2),  # double room (full), part paid
    ("PES1UG24CS003", "Karan", "Patel", "ME", 3),  # double room (full), nothing paid
    ("PES1UG24CS004", "Meera", "Iyer", "CSE", 1),  # triple room (space left), part paid
    ("PES1UG24CS005", "Rohan", "Khan", "CE", 1),  # pending application with preferences
    ("PES1UG24CS006", "Sana", "Das", "EEE", 1),  # pending application, no preferences
    ("PES1UG24CS007", "Vikram", "Nair", "CSE", 3),  # rejected application
    ("PES1UG24CS008", "Anita", "Gupta", "ECE", 2),  # no room, no application
]


class Command(BaseCommand):
    help = "Seed a small demo data set covering every functional requirement."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="Demo@12345", help="Password for all demo logins.")

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.filter(srn=ADMIN_SRN).exists():
            self.stdout.write("Demo story already seeded; nothing changed.")
            return
        password = options["password"]
        now = timezone.now()
        today = timezone.localdate()

        admin = User.objects.create_user(
            ADMIN_SRN, "admin@hms-demo.example", password, first_name="Hostel", last_name="Warden",
            contact_number="9800000000", role=User.Role.ADMIN, is_staff=True,
        )
        s = {}
        for i, (srn, first, last, branch, year) in enumerate(STUDENTS, 1):
            s[i] = User.objects.create_user(
                srn, f"{first.lower()}.{last.lower()}@hms-demo.example", password,
                first_name=first, last_name=last, contact_number=f"98765432{i:02d}",
                branch=branch, year_of_study=year,
            )

        block_a = Block.objects.create(name="Demo Block A", number_of_floors=3)
        block_b = Block.objects.create(name="Demo Block B", number_of_floors=2)

        def room(block, number, floor, kind, capacity, fee):
            return Room.objects.create(
                block=block, room_number=number, floor=floor, room_type=kind,
                capacity=capacity, monthly_fee=Decimal(fee),
            )

        T = Room.RoomType
        a101 = room(block_a, "101", 1, T.SINGLE, 1, 7000)
        a102 = room(block_a, "102", 1, T.DOUBLE, 2, 5500)
        a103 = room(block_a, "103", 1, T.TRIPLE, 3, 4500)
        room(block_a, "201", 2, T.DOUBLE, 2, 5500)  # vacant
        room(block_a, "202", 2, T.SINGLE, 1, 7000)  # vacant
        room(block_b, "101", 1, T.TRIPLE, 3, 4500)  # vacant
        room(block_b, "201", 2, T.DOUBLE, 2, 5500)  # vacant

        # FR-4: allotments (occupied_count kept in step) and applications.
        for student, r in [(1, a101), (2, a102), (3, a102), (4, a103)]:
            RoomAllocation.objects.create(student=s[student], room=r)
            Room.objects.filter(pk=r.pk).update(occupied_count=r.allocations.count())
            RoomApplication.objects.create(student=s[student], status=RoomApplication.Status.ALLOTTED)
        RoomApplication.objects.create(
            student=s[5], preferred_block=block_b, preferred_room_type=T.TRIPLE
        )
        RoomApplication.objects.create(student=s[6])
        RoomApplication.objects.create(student=s[7], status=RoomApplication.Status.REJECTED)

        # FR-5: fees; amount due is the room's monthly fee for the term.
        for student, r, paid in [(1, a101, 1), (2, a102, Decimal("0.5")), (3, a102, 0), (4, a103, Decimal("0.4"))]:
            record = FeeRecord.objects.create(
                student=s[student], room=r, term=TERM, amount_due=FeeRecord.term_fee_for(r)
            )
            if paid:
                Payment.objects.create(
                    fee_record=record, amount=record.amount_due * Decimal(paid),
                    paid_on=today - timedelta(days=7), recorded_by=admin,
                )

        # FR-6: one complaint per status; room is the student's room at the time (FR-6.2).
        C, St = Complaint.Category, Complaint.Status
        for student, r, cat, status, text in [
            (1, a101, C.ELECTRICAL, St.OPEN, "Ceiling fan makes a loud noise and stops at night."),
            (2, a102, C.PLUMBING, St.IN_PROGRESS, "Bathroom tap is leaking."),
            (3, a102, C.INTERNET, St.OPEN, "Wi-Fi drops every few minutes."),
            (4, a103, C.CLEANING, St.RESOLVED, "Corridor outside the room was not cleaned."),
            (4, a103, C.FURNITURE, St.OPEN, "Study table drawer is broken."),
        ]:
            Complaint.objects.create(
                student=s[student], room=r, category=cat, status=status, description=text
            )

        # FR-7: two visitors still inside, one already left.
        Visitor.objects.create(
            host=s[1], name="Ramesh Sharma", phone="9811111111", purpose="Parent visit",
            entered_at=now - timedelta(hours=2),
        )
        Visitor.objects.create(
            host=s[4], name="Lata Iyer", phone="9822222222", purpose="Bringing documents",
            entered_at=now - timedelta(hours=1),
        )
        Visitor.objects.create(
            host=s[2], name="Suresh Rao", phone="9833333333", purpose="Dropping a parcel",
            entered_at=now - timedelta(hours=5), exited_at=now - timedelta(hours=4),
        )

        self.stdout.write(self.style.SUCCESS("Demo story seeded."))
        self.stdout.write(
            f"\nAll logins use password: {password}\n"
            f"  Admin:   {ADMIN_SRN}\n"
            "  Student: PES1UG24CS001 (single room, paid, complaint open, visitor inside)\n"
            "           PES1UG24CS003 (double room, unpaid, complaint open)\n"
            "           PES1UG24CS005 (pending application, no room: apply / blocked visitor)\n"
            "           PES1UG24CS008 (no room, no application: use for FR-2/FR-4.1 and FR-7.3)\n"
            f"Room full for FR-4.3: Demo Block A 101 and 102. Vacant: A 201/202, B 101/201.\n"
        )
