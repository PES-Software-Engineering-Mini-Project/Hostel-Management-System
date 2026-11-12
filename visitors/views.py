from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required, student_required

from .forms import VisitorFilterForm, VisitorForm
from .models import Visitor


@student_required
def register_visitor(request):
    # FR-7.5: a visitor entry needs a host student who currently holds a room.
    if getattr(request.user, "room_allocation", None) is None:
        messages.error(
            request, "You need an allotted room before you can register a visitor."
        )
        return redirect("student-dashboard")
    form = VisitorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        visitor = form.save(commit=False)
        visitor.host = request.user  # never taken from the form (NFR-3)
        visitor.save()  # entry_time is not in the form, so the server clock sets it (FR-7.2)
        messages.success(request, f"{visitor.name} has been registered as your visitor.")
        return redirect("visitors:my-visitors")
    return render(request, "visitors/visitor_form.html", {"form": form})


@student_required
def my_visitors(request):
    # Starting from the student's own visitors keeps their list private (NFR-3).
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
def check_out_visitor(request, pk):
    visitor = get_object_or_404(Visitor, pk=pk)
    try:
        visitor.check_out()
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, f"{visitor.name} has been checked out.")
    return redirect("visitors:visitor-list")
