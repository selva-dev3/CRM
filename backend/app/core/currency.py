import re

DEFAULT_CURRENCY_CODE = "INR"
CURRENCY_CODE_PATTERN = re.compile(r"^[A-Z]{3}$")
# Keep this set aligned with the frontend runtime's supported currency values.
SUPPORTED_CURRENCY_CODES = frozenset(
    """
    AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BRL
    BSD BTN BWP BYN BZD CAD CDF CHF CLP CNY COP CRC CUC CUP CVE CZK DJF DKK DOP DZD
    EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD HNL HRK HTG HUF IDR
    ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR
    LRD LSL LYD MAD MDL MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN MYR MZN NAD NGN NIO
    NOK NPR NZD OMR PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK
    SGD SHP SLE SLL SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS UAH
    UGX USD UYU UZS VES VND VUV WST XAF XCD XCG XDR XOF XPF XSU YER ZAR ZMW ZWG ZWL
    """.split()
)


def normalize_currency_code(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Currency must be a three-letter ISO code.")

    normalized = value.strip().upper()
    if (
        not CURRENCY_CODE_PATTERN.fullmatch(normalized)
        or normalized not in SUPPORTED_CURRENCY_CODES
    ):
        raise ValueError("Currency must be a three-letter ISO code.")
    return normalized


def normalize_currency_code_or_default(value: object, default: str = DEFAULT_CURRENCY_CODE) -> str:
    try:
        return normalize_currency_code(value)
    except ValueError:
        return default
