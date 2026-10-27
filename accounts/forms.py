from django.contrib.auth.forms import AuthenticationForm
from django import forms


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
