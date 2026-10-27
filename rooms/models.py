
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


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
        if self.number_of_floors < 1:
            raise ValidationError({
                "number_of_floors": "A block must have at least one floor."
            })


class Room(models.Model):
    class RoomType(models.TextChoices):
        SINGLE = "Single", "Single"
        DOUBLE = "Double", "Double"
        TRIPLE = "Triple", "Triple"
        DORMITORY = "Dormitory", "Dormitory"

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

        if self.block_id and self.floor > self.block.number_of_floors:
            errors["floor"] = (
                "Floor cannot exceed the block's number of floors."
            )

        expected_capacity = {
            self.RoomType.SINGLE: 1,
            self.RoomType.DOUBLE: 2,
            self.RoomType.TRIPLE: 3,
        }

        if self.room_type in expected_capacity:
            expected = expected_capacity[self.room_type]
            if self.capacity != expected:
                errors["capacity"] = (
                    f"{self.room_type} rooms must have capacity {expected}."
                )

        if self.occupied_count > self.capacity:
            errors["occupied_count"] = (
                "Occupied count cannot exceed room capacity."
            )

        if errors:
            raise ValidationError(errors)
