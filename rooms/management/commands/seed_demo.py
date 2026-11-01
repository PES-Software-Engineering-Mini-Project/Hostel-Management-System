"""Seed realistic demo data for development and NFR-2 performance checks (NFR-2).

Creates blocks with rooms, students, fee records with payments and complaints
at a configurable scale, without touching existing rows. Safe to re-run:
existing SRNs, blocks and fee records are skipped.
"""

import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from complaints.models import Complaint
from fees.models import FeeRecord, Payment
from rooms.models import Block, Room

FIRST_NAMES = ["Aarav", "Diya", "Karan", "Meera", "Rohan", "Sana", "Vikram", "Anita"]
LAST_NAMES = ["Sharma", "Rao", "Patel", "Iyer", "Khan", "Das", "Nair", "Gupta"]
BRANCHES = ["CSE", "ECE", "ME", "CE", "EEE"]
TERMS = ["2026-27 Odd Semester"]


class Command(BaseCommand):
    help = "Seed demo blocks, rooms, students, fees and complaints for performance checks."

    def add_arguments(self, parser):
        parser.add_argument("--blocks", type=int, default=5)
        parser.add_argument("--rooms-per-block", type=int, default=40)
        parser.add_argument("--students", type=int, default=300)
        parser.add_argument("--complaints", type=int, default=120)
        parser.add_argument(
            "--password",
            default="seeded-student-password",
            help="Shared password for seeded students (demo data only).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(20261030)
        User = get_user_model()

        blocks = []
        for i in range(options["blocks"]):
            block, _ = Block.objects.get_or_create(
                name=f"Block {chr(ord('A') + i)}", defaults={"number_of_floors": 4}
            )
            blocks.append(block)

        rooms = []
        for block in blocks:
            existing = set(block.rooms.values_list("room_number", flat=True))
            for i in range(options["rooms_per_block"]):
                room_number = f"{i // 10 + 1}{i % 10:02d}"
                if room_number in existing:
                    continue
                room_type = rng.choice(list(Room.RoomType))
                capacity = {
                    Room.RoomType.SINGLE: 1,
                    Room.RoomType.DOUBLE: 2,
                    Room.RoomType.TRIPLE: 3,
                }[room_type]
                rooms.append(
                    Room(
                        block=block,
                        room_number=room_number,
                        floor=i // 10 + 1,
                        room_type=room_type,
                        capacity=capacity,
                        monthly_fee=Decimal(rng.choice([3500, 4500, 5500, 7000])),
                    )
                )
        Room.objects.bulk_create(rooms)

        existing_srns = set(User.objects.values_list("srn", flat=True))
        students = []
        for i in range(options["students"]):
            srn = f"PES1UG23CS{100 + i:03d}"
            if srn in existing_srns:
                continue
            students.append(
                User(
                    srn=srn,
                    email=f"seeded.student{i}@example.com",
                    first_name=rng.choice(FIRST_NAMES),
                    last_name=rng.choice(LAST_NAMES),
                    contact_number=f"98{rng.randint(10000000, 99999999)}",
                    branch=rng.choice(BRANCHES),
                    year_of_study=rng.randint(1, 4),
                    role=User.Role.STUDENT,
                )
            )
        for student in students:
            student.set_password(options["password"])
        User.objects.bulk_create(students)
        students = list(
            User.objects.filter(role=User.Role.STUDENT, email__startswith="seeded.")
        )

        admin_user = User.objects.filter(role=User.Role.ADMIN).first()
        fee_records = []
        for student in students:
            for term in TERMS:
                fee_records.append(
                    FeeRecord(
                        student=student,
                        term=term,
                        amount_due=Decimal(rng.choice([18000, 22000, 25000])),
                    )
                )
        FeeRecord.objects.bulk_create(fee_records, ignore_conflicts=True)

        payments = []
        if admin_user:
            for record in FeeRecord.objects.filter(student__in=students):
                if rng.random() < 0.7:
                    payments.append(
                        Payment(
                            fee_record=record,
                            amount=record.amount_due / 2,
                            recorded_by=admin_user,
                        )
                    )
            Payment.objects.bulk_create(payments)

        complaints = []
        categories = list(Complaint.Category)
        for i in range(options["complaints"]):
            complaints.append(
                Complaint(
                    student=rng.choice(students),
                    category=rng.choice(categories),
                    description=f"Seeded complaint {i}: needs attention.",
                    status=rng.choice(list(Complaint.Status)),
                )
            )
        Complaint.objects.bulk_create(complaints)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(blocks)} blocks, {Room.objects.count()} rooms, "
                f"{len(students)} students, {FeeRecord.objects.count()} fee records, "
                f"{Complaint.objects.count()} complaints."
            )
        )
