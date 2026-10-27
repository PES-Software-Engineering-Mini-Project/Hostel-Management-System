
from django.urls import path
from django.contrib.auth import views as auth_views

from . import views

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", auth_views.LoginView.as_view(
        template_name="accounts/login.html"
    ), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
    path("students/", views.student_list, name="student_list"),
    path(
        "students/<int:student_id>/edit/",
        views.edit_student,
        name="edit_student",
    ),
]
