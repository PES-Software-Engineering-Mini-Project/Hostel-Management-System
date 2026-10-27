from django.urls import path

from . import views


urlpatterns = [
    path("login/", views.RoleBasedLoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/student/", views.student_dashboard, name="student-dashboard"),
    path("dashboard/admin/", views.admin_dashboard, name="admin-dashboard"),
]
