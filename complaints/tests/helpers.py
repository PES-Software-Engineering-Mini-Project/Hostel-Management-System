from django.contrib.auth import get_user_model

from complaints.models import Complaint


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
