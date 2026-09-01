import re

DEFAULT_LOCALE = "en"
LOCALE_PATTERN = re.compile(
    r"^[A-Za-z]{2,3}"
    r"(?:-[A-Za-z]{4})?"
    r"(?:-(?:[A-Za-z]{2}|[0-9]{3}))?"
    r"(?:-(?:[A-Za-z0-9]{5,8}|[0-9][A-Za-z0-9]{3}))*$"
)


def normalize_locale_or_default(value: object, default: str = DEFAULT_LOCALE) -> str:
    if not isinstance(value, str):
        return default

    normalized = value.strip()
    return normalized if LOCALE_PATTERN.fullmatch(normalized) else default
