from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from complaints.models import Complaint
from fees.models import FeeRecord
from rooms.models import Room

from .decorators import admin_required, student_required
from .forms import (
    AdminStudentForm,
    SRNAuthenticationForm,
    StudentProfileForm,
    StudentSearchForm,
    StudentRegistrationForm,
)
from .models import User


ZERO = Decimal("0.00")
PERCENTAGE_QUANTUM = Decimal("0.1")


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
    """Show live, role-protected summary metrics for the hostel administrator."""
    room_totals = Room.objects.aggregate(
        total_rooms=Count("id"),
        occupied_rooms=Count("id", filter=Q(occupied_count__gt=0)),
        total_beds=Sum("capacity"),
        occupied_beds=Sum("occupied_count"),
    )
    total_beds = room_totals["total_beds"] or 0
    occupied_beds = room_totals["occupied_beds"] or 0
    occupancy_percentage = (
        (Decimal(occupied_beds) * 100 / Decimal(total_beds)).quantize(
            PERCENTAGE_QUANTUM, rounding=ROUND_HALF_UP
        )
        if total_beds
        else Decimal("0.0")
    )

    students_with_dues = set()
    total_amount_owed = ZERO
    for fee_record in FeeRecord.objects.with_totals().only("student_id", "amount_due"):
        balance = fee_record.amount_due - fee_record.total_paid
        if balance > ZERO:
            students_with_dues.add(fee_record.student_id)
            total_amount_owed += balance

    active_complaints = Complaint.objects.filter(
        status__in=[Complaint.Status.OPEN, Complaint.Status.IN_PROGRESS]
    ).count()

    context = {
        "total_rooms": room_totals["total_rooms"],
        "occupied_rooms": room_totals["occupied_rooms"],
        "occupancy_percentage": occupancy_percentage,
        "students_with_dues": len(students_with_dues),
        "total_amount_owed": total_amount_owed,
        "active_complaints": active_complaints,
    }
    return render(request, "accounts/admin_dashboard.html", context)


@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")


@student_required
def profile_edit(request):
    """Edit the signed-in student's own contact details (FR-2.3)."""
    form = StudentProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your profile has been updated.")
        return redirect("profile-edit")
    return render(request, "accounts/profile_form.html", {"form": form})


@admin_required
def student_list(request):
    search_form = StudentSearchForm(request.GET)
    students = search_form.filter(User.objects.filter(role=User.Role.STUDENT)).order_by("srn")
    return render(
        request,
        "accounts/student_list.html",
        {"students": students, "search_form": search_form},
    )


@admin_required
def student_edit(request, pk):
    student = get_object_or_404(User, pk=pk, role=User.Role.STUDENT)
    form = AdminStudentForm(request.POST or None, instance=student)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Record for {student.srn} has been updated.")
        return redirect("student-list")
    return render(
        request, "accounts/student_form.html", {"form": form, "student": student}
    )
