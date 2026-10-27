
from django import forms
from django.contrib.auth.models import User
from django.db import transaction

from .models import StudentProfile


class StudentRegistrationForm(forms.Form):
    srn = forms.CharField(max_length=13)
    name = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=15)
    password = forms.CharField(
        widget=forms.PasswordInput,
        min_length=8,
    )

    def clean_srn(self):
        srn = self.cleaned_data["srn"].strip().upper()
        if StudentProfile.objects.filter(srn__iexact=srn).exists():
            raise forms.ValidationError("This SRN is already registered.")
        return srn

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email

    @transaction.atomic
    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data["srn"],
            first_name=self.cleaned_data["name"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password"],
        )
        StudentProfile.objects.create(
            user=user,
            srn=self.cleaned_data["srn"],
            phone=self.cleaned_data["phone"],
        )
        return user
