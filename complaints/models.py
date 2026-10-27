
from django.conf import settings
from django.db import models


class Complaint(models.Model):
    CATEGORY_CHOICES = [
        ("Electrical", "Electrical"),
        ("Plumbing", "Plumbing"),
        ("Cleaning", "Cleaning"),
        ("Internet", "Internet"),
        ("Other", "Other"),
    ]

    STATUS_CHOICES = [
        ("Open", "Open"),
        ("In Progress", "In Progress"),
        ("Resolved", "Resolved"),
    ]

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="hostel_complaints",
    )
    room = models.CharField(max_length=30)
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
    )
    description = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Open",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category} - {self.student.username} ({self.status})"
