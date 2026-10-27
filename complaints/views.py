
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from .models import Complaint


@login_required
def create_complaint(request):
    if request.user.is_staff or request.user.is_superuser:
        raise PermissionDenied

    if request.method == "POST":
        category = request.POST.get("category", "")
        description = request.POST.get("description", "").strip()
        room = request.POST.get("room", "").strip()

        valid_categories = dict(Complaint.CATEGORY_CHOICES)

        if category not in valid_categories:
            messages.error(request, "Please select a valid category.")
        elif not description or not room:
            messages.error(request, "Room and description are required.")
        else:
            Complaint.objects.create(
                student=request.user,
                room=room,
                category=category,
                description=description,
            )
            messages.success(request, "Complaint submitted successfully.")
            return redirect("my_complaints")

    return render(
        request,
        "complaints/create.html",
        {"categories": Complaint.CATEGORY_CHOICES},
    )


@login_required
def my_complaints(request):
    if request.user.is_staff or request.user.is_superuser:
        raise PermissionDenied

    complaints = Complaint.objects.filter(
        student=request.user
    ).order_by("-created_at")

    return render(
        request,
        "complaints/my_complaints.html",
        {"complaints": complaints},
    )


@login_required
def admin_complaints(request):
    if not (request.user.is_staff or request.user.is_superuser):
        raise PermissionDenied

    complaints = Complaint.objects.select_related(
        "student"
    ).order_by("-created_at")

    if request.method == "POST":
        complaint_id = request.POST.get("complaint_id")
        status = request.POST.get("status")

        allowed_transitions = {
            "Open": "In Progress",
            "In Progress": "Resolved",
        }

        complaint = get_object_or_404(
            Complaint, pk=complaint_id
        )

        if allowed_transitions.get(complaint.status) != status:
            messages.error(
                request,
                "Invalid status transition.",
            )
        else:
            complaint.status = status
            complaint.save(update_fields=["status"])
            messages.success(request, "Complaint status updated.")

        return redirect("admin_complaints")

    return render(
        request,
        "complaints/admin_list.html",
        {"complaints": complaints},
    )
