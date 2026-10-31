
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.conf import settings


class Block(models.Model):
    name = models.CharField(max_length=100, unique=True)
    number_of_floors = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()

        if self.pk and self.number_of_floors is not None:
            highest_room_floor = self.rooms.aggregate(
                highest=models.Max("floor")
            )["highest"]

            if (
                highest_room_floor is not None
                and self.number_of_floors < highest_room_floor
            ):
                raise ValidationError({
                    "number_of_floors": (
                        "Cannot reduce the number of floors below "
                        "the floor of an existing room."
                    )
                })


class RoomQuerySet(models.QuerySet):
    def delete(self):
        if self.filter(occupied_count__gt=0).exists():
            raise ValidationError(
                "Rooms with current occupants cannot be deleted."
            )
        return super().delete()


class Room(models.Model):
    class RoomType(models.TextChoices):
        SINGLE = "Single", "Single"
        DOUBLE = "Double", "Double"
        TRIPLE = "Triple", "Triple"

    block = models.ForeignKey(
        Block,
        on_delete=models.PROTECT,
        related_name="rooms",
    )
    room_number = models.CharField(max_length=20)
    floor = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )
    room_type = models.CharField(
        max_length=20,
        choices=RoomType.choices,
    )
    capacity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )
    monthly_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    occupied_count = models.PositiveIntegerField(default=0)

    objects = RoomQuerySet.as_manager()

    class Meta:
        ordering = ["block__name", "floor", "room_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["block", "room_number"],
                name="unique_room_number_per_block",
            ),
        ]

    def __str__(self):
        return f"{self.block.name} - Room {self.room_number}"

    def clean(self):
        super().clean()
        errors = {}

        if (
            self.block_id
            and self.floor is not None
            and self.block.number_of_floors is not None
            and self.floor > self.block.number_of_floors
        ):
            errors["floor"] = (
                "Floor cannot exceed the block's number of floors."
            )

        expected_capacity = {
            self.RoomType.SINGLE: 1,
            self.RoomType.DOUBLE: 2,
            self.RoomType.TRIPLE: 3,
        }

        if self.room_type in expected_capacity and self.capacity is not None:
            expected = expected_capacity[self.room_type]
            if self.capacity != expected:
                errors["capacity"] = (
                    f"{self.room_type} rooms must have capacity {expected}."
                )

        if (
            self.occupied_count is not None
            and self.capacity is not None
            and self.occupied_count > self.capacity
        ):
            errors["occupied_count"] = (
                "Occupied count cannot exceed room capacity."
            )

        if errors:
            raise ValidationError(errors)

    def delete(self, *args, **kwargs):
        if self.occupied_count > 0:
            raise ValidationError(
                "A room with current occupants cannot be deleted."
            )
        return super().delete(*args, **kwargs)

class RoomApplication(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ALLOTTED = "allotted", "Allotted"
        REJECTED = "rejected", "Rejected"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="room_applications",
    )
    preferred_block = models.ForeignKey(
        Block,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="room_applications",
    )
    preferred_room_type = models.CharField(
        max_length=20,
        choices=Room.RoomType.choices,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["applied_at"]

    def __str__(self):
        return f"{self.student.srn} - {self.get_status_display()}"


class RoomAllocation(models.Model):
    student = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="room_allocation",
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    allocated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.srn} - {self.room}"
