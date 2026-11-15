from decimal import Decimal

from django.contrib.auth import get_user_model

from complaints.models import Complaint
from fees.models import FeeRecord, Payment
from rooms.models import Block, Room


def make_user(srn, role=None, **extra):
    User = get_user_model()
    return User.objects.create_user(
        srn=srn,
        email=f"{srn.lower()}@example.com",
        password="test-password-123",
        first_name=extra.pop("first_name", "Test"),
        last_name=extra.pop("last_name", srn),
        contact_number="9876543210",
        role=role or User.Role.STUDENT,
        **extra,
    )


def make_admin(srn="PES1UG23AD001"):
    return make_user(srn, role=get_user_model().Role.ADMIN)


def make_room(block, room_number, floor=1, room_type=Room.RoomType.DOUBLE, occupied=0, fee="5000"):
    capacity = {Room.RoomType.SINGLE: 1, Room.RoomType.DOUBLE: 2, Room.RoomType.TRIPLE: 3}
    return Room.objects.create(
        block=block,
        room_number=room_number,
        floor=floor,
        room_type=room_type,
        capacity=capacity[room_type],
        monthly_fee=Decimal(fee),
        occupied_count=occupied,
    )


def make_block(name="A Block", floors=3):
    return Block.objects.create(name=name, number_of_floors=floors)


def make_fee(student, amount_due, paid=(), recorded_by=None, term="2026-27 Odd", room=None):
    record = FeeRecord.objects.create(
        student=student, term=term, amount_due=Decimal(amount_due), room=room
    )
    for amount in paid:
        Payment.objects.create(fee_record=record, amount=Decimal(amount), recorded_by=recorded_by)
    return record


def make_complaint(student, category="plumbing", status=Complaint.Status.OPEN):
    return Complaint.objects.create(
        student=student, category=category, description="Needs fixing.", status=status
    )
