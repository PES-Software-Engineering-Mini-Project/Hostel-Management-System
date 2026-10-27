from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
from django.db import models
from django.utils import timezone

DESCRIPTION_MAX_LENGTH = 500


class Complaint(models.Model):
    """A maintenance complaint raised by a student (FR-6.1).

    The student's room (FR-6.2) is not stored yet. It needs room allocation, which arrives
    with SCRUM-9 in Sprint 2.
    """

    class Category(models.TextChoices):
        ELECTRICAL = "electrical", "Electrical"
        PLUMBING = "plumbing", "Plumbing"
        CLEANING = "cleaning", "Cleaning"
        FURNITURE = "furniture", "Furniture"
        INTERNET = "internet", "Internet"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        RESOLVED = "resolved", "Resolved"

    # Forward-only, one step at a time (FR-6.4). A status missing from this map is final.
    NEXT_STATUS = {Status.OPEN: Status.IN_PROGRESS, Status.IN_PROGRESS: Status.RESOLVED}

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="complaints",
        limit_choices_to={"role": "student"},
    )
    category = models.CharField(max_length=30, choices=Category.choices)
    description = models.TextField(validators=[MaxLengthValidator(DESCRIPTION_MAX_LENGTH)])
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN)
    raised_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-raised_at", "-pk"]

    def __str__(self):
        return f"{self.student.srn} - {self.get_category_display()} ({self.get_status_display()})"

    def change_status(self, new_status):
        """Move to the next status only. Skipping, going back or repeating raises (FR-6.4)."""
        next_status = self.NEXT_STATUS.get(self.status)
        if next_status is None or next_status != new_status:
            new_label = dict(self.Status.choices).get(new_status, new_status)
            raise ValidationError(
                f"A complaint cannot move from {self.get_status_display()} to {new_label}."
            )
        # The status in the WHERE clause makes a second admin's stale request fail
        # instead of silently overwriting the first admin's change.
        moved = Complaint.objects.filter(pk=self.pk, status=self.status).update(
            status=new_status, updated_at=timezone.now()
        )
        if not moved:
            raise ValidationError("This complaint was changed by someone else. Reload and retry.")
        self.refresh_from_db(fields=["status", "updated_at"])
