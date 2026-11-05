from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

PHONE_VALIDATOR = RegexValidator(
    r"^\+?[0-9 \-]{7,15}$", "Enter a phone number with 7 to 15 digits (spaces, dashes and a leading + are fine)."
)


class Visitor(models.Model):
    """A visitor to a student, logged at entry and checked out by an admin (FR-7).

    Entry and exit times come from the server clock, never from the browser (FR-7.2, FR-7.3).
    """

    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="visitors",
        limit_choices_to={"role": "student"},
    )
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, validators=[PHONE_VALIDATOR])
    purpose = models.CharField(max_length=200)
    entered_at = models.DateTimeField(default=timezone.now, editable=False)
    exited_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-entered_at", "-pk"]
        indexes = [
            models.Index(fields=["exited_at"], name="visitor_exited_idx"),  # "still inside" (FR-7.4)
            models.Index(fields=["-entered_at"], name="visitor_entered_idx"),  # newest first
        ]

    def __str__(self):
        return f"{self.name} visiting {self.host.srn}"

    @property
    def on_premises(self):
        return self.exited_at is None

    def clean(self):
        """FR-7.5: the host must be a student who currently holds a room."""
        super().clean()
        if self.host_id and getattr(self.host, "room_allocation", None) is None:
            raise ValidationError(
                "A visitor can only be registered by a student who currently has a room."
            )

    def check_out(self):
        """Record the exit time (FR-7.3). Checking out twice raises."""
        # exited_at IS NULL in the WHERE clause means a second admin acting at the same
        # time updates no row and is rejected instead of overwriting the first exit time.
        moved = Visitor.objects.filter(pk=self.pk, exited_at__isnull=True).update(
            exited_at=timezone.now()
        )
        if not moved:
            raise ValidationError("This visitor has already been checked out.")
        self.refresh_from_db(fields=["exited_at"])
