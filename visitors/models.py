from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
from django.db import models
from django.conf import settings
from django.utils import timezone

PURPOSE_MAX_LENGTH = 200


class Visitor(models.Model):
    """A visitor log entry for a host student (SRS 5.7, FR-7.1).

    Entry and exit times come from the server clock (FR-7.2, FR-7.3), never from
    a form. A visitor with no exit time is still on the premises (FR-7.4).
    """

    name = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=15)
    purpose = models.TextField(validators=[MaxLengthValidator(PURPOSE_MAX_LENGTH)])
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="visitors",
        limit_choices_to={"role": "student"},
    )
    entry_time = models.DateTimeField(auto_now_add=True)
    exit_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-entry_time", "-pk"]

    def __str__(self):
        return f"{self.name} (host {self.host.srn})"

    @property
    def is_inside(self):
        return self.exit_time is None

    def check_out(self):
        """Record the exit time from the server clock (FR-7.3). Checking out twice raises."""
        if self.exit_time is not None:
            raise ValidationError(f"{self.name} has already checked out.")
        # The exit_time IS NULL in the WHERE clause makes a second admin's stale
        # request fail instead of silently moving the first admin's exit time.
        updated = Visitor.objects.filter(pk=self.pk, exit_time__isnull=True).update(
            exit_time=timezone.now()
        )
        if not updated:
            raise ValidationError("This visitor was checked out by someone else. Reload and retry.")
        self.refresh_from_db(fields=["exit_time"])
