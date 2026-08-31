import re

DEFAULT_CURRENCY_CODE = "INR"
CURRENCY_CODE_PATTERN = re.compile(r"^[A-Z]{3}$")


def normalize_currency_code(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Currency must be a three-letter ISO code.")

    normalized = value.strip().upper()
    if not CURRENCY_CODE_PATTERN.fullmatch(normalized):
        raise ValueError("Currency must be a three-letter ISO code.")
    return normalized


def normalize_currency_code_or_default(value: object, default: str = DEFAULT_CURRENCY_CODE) -> str:
    try:
        return normalize_currency_code(value)
    except ValueError:
        return default
