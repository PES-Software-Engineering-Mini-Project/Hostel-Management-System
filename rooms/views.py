
from django.shortcuts import redirect, render

from accounts.decorators import admin_required

from .forms import BlockForm, RoomForm
from .models import Block, Room


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
