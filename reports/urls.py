from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.report_index, name="index"),
    path("<slug:slug>/", views.report_detail, name="detail"),
    path("<slug:slug>/csv/", views.report_csv, name="csv"),
]
