from django.contrib.auth import get_user_model

from rooms.models import Block, Room, RoomAllocation
from visitors.models import Visitor


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


def make_admin(srn="PES1UG23AD901"):
    return make_user(srn, role=get_user_model().Role.ADMIN)


def give_room(student, number="101"):
    block, _ = Block.objects.get_or_create(name="Block A", defaults={"number_of_floors": 3})
    room = Room.objects.create(
        block=block, room_number=number, floor=1,
        room_type=Room.RoomType.DOUBLE, capacity=2, monthly_fee="1000.00",
    )
    RoomAllocation.objects.create(student=student, room=room)
    return room


def make_visitor(host, name="Meera Rao", **extra):
    return Visitor.objects.create(
        host=host, name=name, phone=extra.pop("phone", "9123456780"),
        purpose=extra.pop("purpose", "Family visit"), **extra,
    )
