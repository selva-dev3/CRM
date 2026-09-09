"""International CRM phone normalization. Formatting never proves ownership."""

import re

import phonenumbers


def normalize_phone(value: str, region: str | None = None, *, provider: bool = False) -> str:
    value = value.strip()
    if not value or len(value) > 64 or not re.fullmatch(r"[+\d\s().-]+", value, re.ASCII):
        raise ValueError("Invalid international phone number")
    if provider:
        # Meta sender identifiers already include an international calling code.
        if not re.fullmatch(r"\d{7,15}", value, re.ASCII):
            raise ValueError("Invalid provider phone number")
        value = "+" + value
    if region and region not in phonenumbers.SUPPORTED_REGIONS:
        raise ValueError("An explicit ISO phone region is required")
    if not value.startswith("+") and not region:
        raise ValueError("Include an international calling code")
    try:
        number = phonenumbers.parse(value, region)
    except phonenumbers.NumberParseException as exc:
        raise ValueError("Invalid international phone number") from exc
    if number.extension or not phonenumbers.is_valid_number(number):
        raise ValueError("Invalid international phone number")
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
