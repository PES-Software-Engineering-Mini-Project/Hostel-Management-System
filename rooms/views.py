

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required, student_required
from .forms import BlockForm, RoomApplicationForm, RoomForm
from .models import (
    Block,
    Room,
    RoomAllocation,
    RoomApplication,
)

@admin_required
def room_list(request):
    rooms = Room.objects.select_related("block").all()
    blocks = Block.objects.all()

    return render(
        request,
        "rooms/room_list.html",
        {"rooms": rooms, "blocks": blocks},
    )


@admin_required
def block_create(request):
    if request.method == "POST":
        form = BlockForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("rooms:room-list")
    else:
        form = BlockForm()

    return render(
        request,
        "rooms/block_form.html",
        {"form": form},
    )


@admin_required
def room_create(request):
    if request.method == "POST":
        form = RoomForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("rooms:room-list")
    else:
        form = RoomForm()

    return render(
        request,
        "rooms/room_form.html",
        {"form": form},
    )


@student_required
def apply_for_room(request):
    existing_allocation = getattr(
        request.user, "room_allocation", None
    )

    if existing_allocation is not None:
        messages.info(request, "You already have an allotted room.")
        return redirect("student-dashboard")

    existing_application = RoomApplication.objects.filter(
        student=request.user,
        status=RoomApplication.Status.PENDING,
    ).exists()

    if existing_application:
        messages.info(request, "You already have a pending room application.")
        return redirect("student-dashboard")

    if request.method == "POST":
        form = RoomApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.student = request.user
            application.save()
            messages.success(request, "Room application submitted successfully.")
            return redirect("student-dashboard")
    else:
        form = RoomApplicationForm()

    return render(
        request,
        "rooms/application_form.html",
        {"form": form},
    )


@admin_required
def pending_applications(request):
    applications = RoomApplication.objects.filter(
        status=RoomApplication.Status.PENDING
    ).select_related("student", "preferred_block")

    rooms = Room.objects.select_related("block").filter(
        occupied_count__lt=F("capacity")
    )

    return render(
        request,
        "rooms/pending_applications.html",
        {
            "applications": applications,
            "rooms": rooms,
        },
    )


@admin_required
@require_POST
def move_student(request, allocation_id):
    try:
        with transaction.atomic():
            allocation = get_object_or_404(
            RoomAllocation.objects.select_for_update().select_related("room"),
            pk=allocation_id,)

            new_room = get_object_or_404(
                Room,
                pk=request.POST.get("room_id"),
            )

            if allocation.room_id == new_room.pk:
                messages.info(request, "The student already occupies this room.")
                return redirect("rooms:allocation-list")

            updated = Room.objects.filter(
                pk=new_room.pk,
                occupied_count__lt=F("capacity"),
            ).update(occupied_count=F("occupied_count") + 1)

            if updated == 0:
                messages.error(request, "The destination room is full.")
                return redirect("rooms:allocation-list")

            Room.objects.filter(
                pk=allocation.room_id,
                occupied_count__gt=0,
            ).update(occupied_count=F("occupied_count") - 1)

            allocation.room = new_room
            allocation.save(update_fields=["room"])

        messages.success(request, "Student moved successfully.")

    except IntegrityError:
        messages.error(request, "The room move could not be completed.")

    return redirect("rooms:allocation-list")


@admin_required
@require_POST
def deallocate_student(request, allocation_id):
    with transaction.atomic():
        allocation = get_object_or_404(
            RoomAllocation.objects.select_related("room"),
            pk=allocation_id,
        )

        Room.objects.filter(
            pk=allocation.room_id,
            occupied_count__gt=0,
        ).update(occupied_count=F("occupied_count") - 1)

        allocation.delete()

    messages.success(request, "Student deallocated successfully.")
    return redirect("rooms:allocation-list")


@admin_required
def allocation_list(request):
    allocations = RoomAllocation.objects.select_related(
        "student", "room", "room__block"
    ).all()

    available_rooms = Room.objects.select_related("block").filter(
        occupied_count__lt=F("capacity")
    )

    return render(
        request,
        "rooms/allocation_list.html",
        {
            "allocations": allocations,
            "available_rooms": available_rooms,
        },
    )



@admin_required
@require_POST
def reject_application(request, application_id):
    with transaction.atomic():
        application = get_object_or_404(
            RoomApplication.objects.select_for_update(),
            pk=application_id,
        )

        if application.status != RoomApplication.Status.PENDING:
            messages.error(
                request,
                "Only pending applications can be rejected.",
            )
            return redirect("rooms:pending-applications")

        application.status = RoomApplication.Status.REJECTED
        application.save(update_fields=["status"])

    messages.success(request, "Room application rejected successfully.")
    return redirect("rooms:pending-applications")


@admin_required
@require_POST
def allot_room(request, application_id):
    try:
        with transaction.atomic():
            application = get_object_or_404(
                RoomApplication.objects.select_for_update(),
                pk=application_id,
            )

            if application.status != RoomApplication.Status.PENDING:
                messages.error(request, "Application is not pending.")
                return redirect("rooms:pending-applications")

            if RoomAllocation.objects.filter(
                student=application.student
            ).exists():
                messages.error(request, "Student already has a room.")
                return redirect("rooms:pending-applications")

            room = get_object_or_404(
                Room,
                pk=request.POST.get("room_id"),
            )

            updated = Room.objects.filter(
                pk=room.pk,
                occupied_count__lt=F("capacity"),
            ).update(
                occupied_count=F("occupied_count") + 1
            )

            if updated == 0:
                messages.error(request, "Room is full.")
                return redirect("rooms:pending-applications")

            RoomAllocation.objects.create(
                student=application.student,
                room=room,
            )

            application.status = RoomApplication.Status.ALLOTTED
            application.save(update_fields=["status"])

        messages.success(request, "Room allotted successfully.")

    except IntegrityError:
        messages.error(request, "Allocation failed. Please check the student's current allocation.")

    return redirect("rooms:pending-applications")