from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .decorators import admin_required, student_required
from .forms import SRNAuthenticationForm, StudentRegistrationForm
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


def register(request):
    """Register a new Student account; roles are never supplied by the browser."""
    if request.user.is_authenticated:
        if request.user.role == User.Role.ADMIN:
            return redirect("admin-dashboard")
        return redirect("student-dashboard")

    form = StudentRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Registration successful. Please sign in with your SRN.")
        return redirect("login")
    return render(request, "accounts/register.html", {"form": form})


@student_required
def student_dashboard(request):
    from rooms.models import RoomApplication

    allocation = getattr(request.user, "room_allocation", None)
    pending_application = RoomApplication.objects.filter(
        student=request.user,
        status=RoomApplication.Status.PENDING,
    ).exists()
    return render(request, "accounts/area.html", {"area_name": "Student area","allocation":allocation,"pending_application":pending_application,})


@admin_required
def admin_dashboard(request):
    return render(request, "accounts/area.html", {"area_name": "Admin area"})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")
