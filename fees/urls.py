from django.urls import path

from . import views

app_name = "fees"

urlpatterns = [
    path("", views.my_fees, name="my-fees"),
    path("manage/", views.fee_list, name="fee-list"),
    path("manage/new/", views.fee_create, name="fee-create"),
    path("manage/<int:pk>/payments/new/", views.record_payment, name="record-payment"),
    path("receipts/<int:pk>/", views.receipt, name="receipt"),
    path("receipts/<int:pk>/download/", views.receipt_download, name="receipt-download"),
]
