"""Phone normalization — single source of truth.

All pydantic schemas import :func:`normalize_phone` from here instead of
keeping their own copy (5 divergent copies removed: client/master/user/otp/auth).
Format: ``+7 (XXX) XXX-XX-XX``. Accepts 10 digits (9991234567) or 11 digits
with trunk 8/7 prefix (89991234567); longer input is truncated to the last
11 digits (country-code prefix tolerant).
"""
import re


def normalize_phone(phone: str) -> str:
    """Normalize phone to +7 (XXX) XXX-XX-XX format."""
    digits = re.sub(r"\D", "", phone)
    if not digits:
        raise ValueError("Введите номер телефона")
    if len(digits) > 11:
        digits = digits[-11:]
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    if not digits.startswith("7"):
        digits = "7" + digits
    if len(digits) != 11:
        raise ValueError("Номер телефона должен содержать 10 цифр")
    return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
