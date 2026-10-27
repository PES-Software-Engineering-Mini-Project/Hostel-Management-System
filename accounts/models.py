
from django.conf import settings
from django.db import models


class StudentProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
    )
    srn = models.CharField(max_length=13, unique=True)
    phone = models.CharField(max_length=15)

    def __str__(self):
        return f"{self.srn} - {self.user.get_full_name()}"
