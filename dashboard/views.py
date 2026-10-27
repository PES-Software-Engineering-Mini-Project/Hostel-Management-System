
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, F, Sum, Value, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from django.shortcuts import render

from complaints.models import Complaint
from .models import Room, RoomAllocation, FeeRecord, RoomApplication


@login_required
def admin_dashboard(request):
    if not (request.user.is_staff or request.user.is_superuser):
        raise PermissionDenied

    # FR-8.1: Room occupancy
    total_rooms = Room.objects.count()

    occupied_rooms = Room.objects.filter(
        allocations__is_active=True
    ).distinct().count()

    occupancy_percentage = (
        round((occupied_rooms / total_rooms) * 100, 2)
        if total_rooms > 0
        else 0
    )

    # FR-8.2: Outstanding fees
    outstanding_balance = ExpressionWrapper(
        F("amount_due") - F("amount_paid"),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )

    fee_data = FeeRecord.objects.filter(
        amount_due__gt=F("amount_paid")
    ).aggregate(
        students_owing=Count("student", distinct=True),
        total_owed=Coalesce(
            Sum(outstanding_balance),
            Value(0),
            output_field=DecimalField(
                max_digits=12,
                decimal_places=2,
            ),
        ),
    )

    # FR-8.3: Complaints
    open_complaints = Complaint.objects.filter(
        status="Open"
    ).count()

    in_progress_complaints = Complaint.objects.filter(
        status="In Progress"
    ).count()

    # FR-8.4: Pending room applications
    pending_applications = RoomApplication.objects.filter(
        status="Pending"
    ).count()

    context = {
        "total_rooms": total_rooms,
        "occupied_rooms": occupied_rooms,
        "occupancy_percentage": occupancy_percentage,
        "students_owing_fees": fee_data["students_owing"],
        "total_amount_owed": fee_data["total_owed"],
        "open_complaints": open_complaints,
        "in_progress_complaints": in_progress_complaints,
        "pending_applications": pending_applications,
    }

    return render(
        request,
        "dashboard/admin_dashboard.html",
        context,
    )
