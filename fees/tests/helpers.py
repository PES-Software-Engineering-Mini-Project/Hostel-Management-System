from decimal import Decimal

from django.contrib.auth import get_user_model

from fees.models import FeeRecord


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


def make_admin(srn="PES1UG23AD001"):
    return make_user(srn, role=get_user_model().Role.ADMIN)


def make_fee_record(student, term="2026-27 Odd", amount_due="50000.00"):
    return FeeRecord.objects.create(student=student, term=term, amount_due=Decimal(amount_due))
