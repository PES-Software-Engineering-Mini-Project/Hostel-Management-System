from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import User

from .forms import FeeRecordForm, PaymentForm
from .models import FeeRecord


def role_required(role):
    """Reject users whose stored role does not match, checked on the server (NFR-3)."""

    def decorator(view):
        @login_required
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.user.role != role:
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


admin_required = role_required(User.Role.ADMIN)
student_required = role_required(User.Role.STUDENT)


@admin_required
def fee_list(request):
    records = FeeRecord.objects.select_related("student").with_totals()
    return render(request, "fees/fee_list.html", {"records": records})


@admin_required
def fee_create(request):
    form = FeeRecordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        record = form.save()
        messages.success(request, f"Fee record added for {record.student.srn} ({record.term}).")
        return redirect("fees:fee-list")
    return render(request, "fees/fee_form.html", {"form": form})


@admin_required
def record_payment(request, pk):
    fee_record = get_object_or_404(FeeRecord.objects.select_related("student"), pk=pk)
    form = PaymentForm(request.POST or None, fee_record=fee_record, recorded_by=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            fee_record.record_payment(
                amount=form.cleaned_data["amount"],
                paid_on=form.cleaned_data["paid_on"],
                recorded_by=request.user,
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(
                request, f"Payment of ₹{form.cleaned_data['amount']} recorded for {fee_record}."
            )
            return redirect("fees:fee-list")
    context = {
        "form": form,
        "fee_record": fee_record,
        "payments": fee_record.payments.select_related("recorded_by"),
    }
    return render(request, "fees/payment_form.html", context)


@student_required
def my_fees(request):
    records = request.user.fee_records.with_totals().prefetch_related("payments")
    return render(request, "fees/my_fees.html", {"records": records})
