from decimal import Decimal

from django.contrib.auth import get_user_model

from complaints.models import Complaint
from rooms.models import Block, Room, RoomAllocation


def make_user(srn, role=None, **extra):
    user_model = get_user_model()
    return user_model.objects.create_user(
        srn=srn,
        email=f"{srn.lower()}@example.com",
        password="test-password-123",
        first_name=extra.pop("first_name", "Test"),
        last_name=extra.pop("last_name", srn),
        contact_number="9876543210",
        role=role or user_model.Role.STUDENT,
        **extra,
    )


def make_admin(srn="PES1UG23AD701"):
    return make_user(srn, role=get_user_model().Role.ADMIN)


def make_complaint(student, category=Complaint.Category.PLUMBING, description="Tap is leaking.", **extra):
    return Complaint.objects.create(
        student=student, category=category, description=description, **extra
    )


def allot_room(student, room_number="101", block_name="A Block"):
    """Give a student an active room allocation for complaint room tagging (FR-6.2)."""
    block, _ = Block.objects.get_or_create(name=block_name, defaults={"number_of_floors": 3})
    room = Room.objects.create(
        block=block,
        room_number=room_number,
        floor=1,
        room_type=Room.RoomType.DOUBLE,
        capacity=2,
        monthly_fee=Decimal("5000.00"),
        occupied_count=1,
    )
    RoomAllocation.objects.create(student=student, room=room)
    return room
