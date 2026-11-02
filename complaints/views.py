from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required, student_required

from .forms import ComplaintFilterForm, ComplaintForm
from .models import Complaint


@student_required
def raise_complaint(request):
    form = ComplaintForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        complaint = form.save(commit=False)
        complaint.student = request.user  # never taken from the form (NFR-3)
        complaint.save()  # status is not in the form, so it always starts as Open (FR-6.3)
        messages.success(request, "Your complaint has been submitted.")
        return redirect("complaints:my-complaints")
    return render(request, "complaints/complaint_form.html", {"form": form})


@student_required
def my_complaints(request):
    # Starting from the student's own complaints keeps their search private (FR-9.5).
    filter_form = ComplaintFilterForm(request.GET)
    complaints = filter_form.filter(request.user.complaints.all())
    return render(
        request,
        "complaints/my_complaints.html",
        {"complaints": complaints, "filter_form": filter_form},
    )


@student_required
def complaint_detail(request, pk):
    # Filtering by student makes someone else's complaint a 404, not a 403 (NFR-3, FR-6.6).
    complaint = get_object_or_404(Complaint, pk=pk, student=request.user)
    return render(request, "complaints/complaint_detail.html", {"complaint": complaint})


@admin_required
def complaint_list(request):
    filter_form = ComplaintFilterForm(request.GET)
    complaints = filter_form.filter(Complaint.objects.select_related("student"))
    return render(
        request,
        "complaints/complaint_list.html",
        {"complaints": complaints, "filter_form": filter_form},
    )


@admin_required
@require_POST
def update_status(request, pk):
    complaint = get_object_or_404(Complaint, pk=pk)
    try:
        complaint.change_status(request.POST.get("status", ""))
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(
            request, f"Complaint #{complaint.pk} is now {complaint.get_status_display()}."
        )
    return redirect("complaints:complaint-list")
