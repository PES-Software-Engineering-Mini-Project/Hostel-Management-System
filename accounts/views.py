
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render

from .forms import StudentRegistrationForm
from .models import StudentProfile


def register(request):
    if request.method == "POST":
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            try:
                form.save()
            except IntegrityError:
                form.add_error(
                    None,
                    "That SRN or email is already registered. Please try again.",
                )
            else:
                messages.success(
                    request,
                    "Registration successful. You can now log in.",
                )
                return redirect("login")
    else:
        form = StudentRegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


@login_required
def profile(request):
    if request.user.is_staff or request.user.is_superuser:
        raise PermissionDenied

    student = get_object_or_404(
        StudentProfile.objects.select_related("user"),
        user=request.user,
    )

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone", "").strip()

        if not name or not email or not phone:
            messages.error(request, "Name, email and phone are required.")
        elif User.objects.filter(email__iexact=email).exclude(
            pk=request.user.pk
        ).exists():
            messages.error(request, "That email is already in use.")
        else:
            request.user.first_name = name
            request.user.email = email
            student.phone = phone
            request.user.save(update_fields=["first_name", "email"])
            student.save(update_fields=["phone"])
            messages.success(request, "Contact details updated.")
            return redirect("profile")

    return render(request, "accounts/profile.html", {"student": student})


@login_required
def student_list(request):
    if not (request.user.is_staff or request.user.is_superuser):
        raise PermissionDenied

    students = StudentProfile.objects.select_related("user").order_by("srn")
    return render(request, "accounts/student_list.html", {"students": students})


@login_required
def edit_student(request, student_id):
    if not (request.user.is_staff or request.user.is_superuser):
        raise PermissionDenied

    student = get_object_or_404(
        StudentProfile.objects.select_related("user"),
        pk=student_id,
    )

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone", "").strip()

        if not name or not email or not phone:
            messages.error(request, "Name, email and phone are required.")
        elif User.objects.filter(email__iexact=email).exclude(
            pk=student.user_id
        ).exists():
            messages.error(request, "That email is already in use.")
        else:
            with transaction.atomic():
                student.user.first_name = name
                student.user.email = email
                student.phone = phone
                student.user.save(update_fields=["first_name", "email"])
                student.save(update_fields=["phone"])
            messages.success(request, "Student details updated.")
            return redirect("student_list")

    return render(
        request,
        "accounts/edit_student.html",
        {"student": student},
    )
