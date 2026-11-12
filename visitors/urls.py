from django.urls import path

from . import views

app_name = "visitors"

urlpatterns = [
    path("", views.my_visitors, name="my-visitors"),
    path("new/", views.register_visitor, name="register"),
    path("manage/", views.visitor_list, name="visitor-list"),
    path("manage/<int:pk>/checkout/", views.check_out_visitor, name="check-out"),
]
