
from django.contrib import admin
from .models import StudentProfile


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("srn", "get_name", "get_email", "phone")
    search_fields = ("srn", "user__first_name", "user__email")

    @admin.display(description="Name")
    def get_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    @admin.display(description="Email")
    def get_email(self, obj):
        return obj.user.email
