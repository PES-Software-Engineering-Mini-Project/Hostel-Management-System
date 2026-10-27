from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST

from .forms import SRNAuthenticationForm
from .models import User


class RoleBasedLoginView(LoginView):
    """Authenticate with Django auth and route users by their stored HMS role."""

    authentication_form = SRNAuthenticationForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        if self.request.user.role == User.Role.ADMIN:
            return reverse("admin-dashboard")
        return reverse("student-dashboard")


@login_required
def student_dashboard(request):
    if request.user.role != User.Role.STUDENT:
        raise PermissionDenied("Admin users cannot access the student area.")
    return render(request, "accounts/area.html", {"area_name": "Student area"})


@login_required
def admin_dashboard(request):
    if request.user.role != User.Role.ADMIN:
        raise PermissionDenied("You do not have permission to access this area.")
    return render(request, "accounts/area.html", {"area_name": "Admin area"})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")
