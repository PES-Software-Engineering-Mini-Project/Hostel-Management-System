
from django.urls import path

from . import views

app_name = "rooms"

urlpatterns = [
    path("", views.room_list, name="room-list"),
    path("blocks/add/", views.block_create, name="block-create"),
    path("add/", views.room_create, name="room-create"),
]
