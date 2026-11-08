import re

from django import forms

from .models import GiftOrder


class GiftOrderForm(forms.ModelForm):
    class Meta:
        model = GiftOrder
        fields = (
            "recipient_full_name",
            "recipient_address",
            "recipient_postal_code",
            "recipient_country",
            "recipient_phone",
            "customer_note",
        )
        labels = {
            "recipient_full_name": "Recipient's full name",
            "recipient_address": "Complete delivery address",
            "recipient_postal_code": "Postal / ZIP code",
            "recipient_country": "Country",
            "recipient_phone": "Recipient's phone number",
            "customer_note": "Delivery note (optional)",
        }
        widgets = {
            "recipient_address": forms.Textarea(attrs={"rows": 3}),
            "customer_note": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "recipient_full_name": "e.g. Adaeze Okafor",
            "recipient_address": "House number, street, city and state",
            "recipient_postal_code": "e.g. 100001",
            "recipient_country": "e.g. Nigeria",
            "recipient_phone": "e.g. +234 800 000 0000",
            "customer_note": "Anything support should know about this delivery",
        }
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "gift-control"
            field.widget.attrs["placeholder"] = placeholders.get(name, "")
        self.fields["recipient_phone"].widget.attrs["inputmode"] = "tel"

    def clean_recipient_phone(self):
        value = " ".join(self.cleaned_data["recipient_phone"].split())
        if not re.fullmatch(r"^\+?[0-9()\s-]{7,25}$", value):
            raise forms.ValidationError("Enter a valid phone number, including the country code.")
        return value

    def clean_recipient_full_name(self):
        value = " ".join(self.cleaned_data["recipient_full_name"].split())
        if len(value.split()) < 2:
            raise forms.ValidationError("Enter the recipient's first and last name.")
        return value