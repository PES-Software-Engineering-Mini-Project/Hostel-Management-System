
from django.urls import path

from . import views

app_name = "rooms"

urlpatterns = [
    path("", views.room_list, name="room-list"),
    path("blocks/add/", views.block_create, name="block-create"),
    path("add/", views.room_create, name="room-create"),
    path("apply/", views.apply_for_room, name="apply"),
    path("applications/",views.pending_applications, name="pending-applications"),
    path("application/<int:application_id>/allot/",views.allot_room,name="allot-room"),
    path("allocations/",views.allocation_list,name="allocation-list"),
    path("allocation/<int:allocation_id>/move/",views.move_student,name="move-student"),
    path("allocation/<int:allocation_id>/deallocate/",views.deallocate_student,name="deallocate-student")
]
