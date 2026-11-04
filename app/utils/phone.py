import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat, PhoneNumberType

SMS_CAPABLE_NUMBER_TYPES = frozenset(
    {PhoneNumberType.MOBILE, PhoneNumberType.FIXED_LINE_OR_MOBILE}
)


def normalize_mobile_number(raw: str) -> str | None:
    candidate = raw.strip()
    if not candidate.startswith("+"):
        return None
    try:
        parsed = phonenumbers.parse(candidate, None)
    except NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    if phonenumbers.number_type(parsed) not in SMS_CAPABLE_NUMBER_TYPES:
        return None
    return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)


def mask_phone(phone: str, visible_digits: int = 4) -> str:
    hidden = max(len(phone) - visible_digits, 0)
    return "*" * hidden + phone[hidden:]
