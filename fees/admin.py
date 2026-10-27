from django.contrib import admin

from .models import FeeRecord, Payment


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ("amount", "paid_on", "recorded_by", "recorded_at")
    readonly_fields = ("recorded_at",)


@admin.register(FeeRecord)
class FeeRecordAdmin(admin.ModelAdmin):
    list_display = ("student", "term", "amount_due", "amount_paid", "balance")
    list_filter = ("term",)
    search_fields = ("student__srn", "student__first_name", "student__last_name", "term")
    inlines = [PaymentInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("student").with_totals()


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("fee_record", "amount", "paid_on", "recorded_by")
    list_filter = ("paid_on",)
    search_fields = ("fee_record__student__srn", "fee_record__term")
