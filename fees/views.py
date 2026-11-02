from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string

from accounts.decorators import admin_required, student_required
from accounts.models import User

from .forms import FeeRecordForm, PaymentForm
from .models import FeeRecord, Payment


@admin_required
def fee_list(request):
    records = FeeRecord.objects.select_related("student", "room__block").with_totals()
    return render(request, "fees/fee_list.html", {"records": records})


@admin_required
def fee_create(request):
    form = FeeRecordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        record = form.save()
        messages.success(
            request,
            f"Fee record added for {record.student.srn} ({record.term}): ₹{record.amount_due} "
            f"for room {record.room.room_number}.",
        )
        return redirect("fees:fee-list")
    return render(request, "fees/fee_form.html", {"form": form})


@admin_required
def record_payment(request, pk):
    fee_record = get_object_or_404(FeeRecord.objects.select_related("student", "room__block"), pk=pk)
    form = PaymentForm(request.POST or None, fee_record=fee_record, recorded_by=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            payment = fee_record.record_payment(
                amount=form.cleaned_data["amount"],
                paid_on=form.cleaned_data["paid_on"],
                recorded_by=request.user,
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(
                request, f"Payment of ₹{payment.amount} recorded for {fee_record}."
            )
            return redirect("fees:receipt", pk=payment.pk)
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


def _receipt_payment(request, pk):
    """Admins can open any receipt; a student only their own (FR-5.6, NFR-3).

    Someone else's receipt is a 404 rather than a 403, so receipt numbers can't be probed.
    """
    payments = Payment.objects.select_related(
        "fee_record__student", "fee_record__room__block", "recorded_by"
    )
    if request.user.role != User.Role.ADMIN:
        payments = payments.filter(fee_record__student=request.user)
    payment = payments.filter(pk=pk).first()
    if payment is None:
        raise Http404("No receipt found.")
    return payment


@login_required
def receipt(request, pk):
    payment = _receipt_payment(request, pk)
    return render(request, "fees/receipt.html", {"payment": payment})


@login_required
def receipt_download(request, pk):
    payment = _receipt_payment(request, pk)
    html = render_to_string("fees/receipt_document.html", {"payment": payment}, request=request)
    response = HttpResponse(html, content_type="text/html; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="hms-receipt-{payment.receipt_number}.html"'
    )
    return response
