from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import User


class SRNAuthenticationForm(AuthenticationForm):
    """Django authentication form labelled for the custom SRN login identifier."""

    username = forms.CharField(
        label="SRN",
        max_length=13,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "username",
                "autocapitalize": "characters",
                "placeholder": "Enter your SRN",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "current-password", "placeholder": "Enter your password"}
        ),
    )
    error_messages = {
        "invalid_login": "Please enter a valid SRN and password.",
        "inactive": "This account is inactive.",
    }

    def clean_username(self):
        return self.cleaned_data["username"].upper()


class StudentRegistrationForm(forms.ModelForm):
    """Creates Student accounts while keeping role and password handling server-side."""

    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    confirm_password = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ["srn", "first_name", "last_name", "email", "contact_number"]
        widgets = {
            "srn": forms.TextInput(
                attrs={"autocomplete": "username", "autocapitalize": "characters"}
            ),
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "contact_number": forms.TextInput(attrs={"autocomplete": "tel"}),
        }

    def clean_srn(self):
        srn = self.cleaned_data["srn"]
        if User.objects.filter(srn__iexact=srn).exists():
            raise ValidationError("An account with this SRN already exists.")
        return srn

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email address already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match.")
            return cleaned_data

        if password:
            candidate = User(
                srn=cleaned_data.get("srn", ""),
                email=cleaned_data.get("email", ""),
                first_name=cleaned_data.get("first_name", ""),
                last_name=cleaned_data.get("last_name", ""),
            )
            try:
                validate_password(password, user=candidate)
            except ValidationError as error:
                self.add_error("password", error)
        return cleaned_data

    def save(self, commit=True):
        if not commit:
            raise ValueError("StudentRegistrationForm must save a complete user account.")
        return User.objects.create_user(
            srn=self.cleaned_data["srn"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            contact_number=self.cleaned_data["contact_number"],
            role=User.Role.STUDENT,
        )
