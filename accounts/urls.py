from django.urls import path

from . import views


urlpatterns = [
    path("login/", views.RoleBasedLoginView.as_view(), name="login"),
    path("register/", views.register, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/student/", views.student_dashboard, name="student-dashboard"),
    path("dashboard/admin/", views.admin_dashboard, name="admin-dashboard"),
]
urlpatterns += [
    path("profile/", views.profile_edit, name="profile-edit"),
    path("students/", views.student_list, name="student-list"),
    path("students/<int:pk>/edit/", views.student_edit, name="student-edit"),
]
