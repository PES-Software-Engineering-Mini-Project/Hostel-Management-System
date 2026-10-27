from django.urls import path

from . import views

app_name = "complaints"

urlpatterns = [
    path("", views.my_complaints, name="my-complaints"),
    path("new/", views.raise_complaint, name="raise"),
    path("<int:pk>/", views.complaint_detail, name="detail"),
    path("manage/", views.complaint_list, name="complaint-list"),
    path("manage/<int:pk>/status/", views.update_status, name="update-status"),
]
