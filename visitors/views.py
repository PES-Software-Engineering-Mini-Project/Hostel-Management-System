from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required, student_required

from .forms import VisitorFilterForm, VisitorForm
from .models import Visitor


@student_required
def register_visitor(request):
    # FR-7.1, FR-7.5. The host is the logged-in student, never taken from the form (NFR-3).
    # Visitor.clean() refuses a student without a room, so the form is invalid for them.
    has_room = getattr(request.user, "room_allocation", None) is not None
    form = VisitorForm(request.POST or None, instance=Visitor(host=request.user))
    if request.method == "POST" and form.is_valid():
        form.save()  # entry time is the server clock (FR-7.2)
        messages.success(request, "Your visitor has been registered.")
        return redirect("visitors:my-visitors")
    return render(request, "visitors/visitor_form.html", {"form": form, "has_room": has_room})


@student_required
def my_visitors(request):
    # Starting from the student's own visitors keeps other students' visitors private.
    visitors = request.user.visitors.all()
    return render(request, "visitors/my_visitors.html", {"visitors": visitors})


@admin_required
def visitor_list(request):
    filter_form = VisitorFilterForm(request.GET)
    visitors = filter_form.filter(Visitor.objects.select_related("host"))
    return render(
        request,
        "visitors/visitor_list.html",
        {"visitors": visitors, "filter_form": filter_form},
    )


@admin_required
@require_POST
def check_out(request, pk):
    visitor = get_object_or_404(Visitor, pk=pk)
    try:
        visitor.check_out()
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, f"{visitor.name} has been checked out.")
    return redirect("visitors:visitor-list")
