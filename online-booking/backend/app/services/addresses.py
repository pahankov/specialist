"""Address helpers shared by the master profile and self-activation.

The cabinet address is free text picked from DaData. A non-empty string is
not enough: the owner's checklist requires at least a house number, otherwise
«Москва, ул. Ленина» would count as a complete workplace address.

The parser is deliberately conservative: it accepts a trailing house number
(«5», «5А», «5/1», «5-7», «д. 5», «вл. 5») and rejects a bare street name.
It does not try to be a full address parser; DaData suggestions carry the
canonical house form, and free-typed text follows the same familiar pattern.
"""
import re
from typing import Optional


_HOUSE_MARKER_RE = re.compile(
    r"\b(?:д|дом|двлд|вл|владение|зд|здание|стр|строение|корп|корпус|к)"
    r"\.?\s*\d",
    re.IGNORECASE,
)

# A trailing number in a comma-separated part, e.g. «ул. Ленина, 5» or
# «ул. Ленина 5А». The optional suffix covers 5/1 and 5-7.
_TRAILING_HOUSE_RE = re.compile(
    r"(?:^|[\s,])(\d+[a-zа-яё]?(?:\s*[/-]\s*\d+[a-zа-яё]?)?)\s*$",
    re.IGNORECASE,
)

_STREET_WORD_RE = re.compile(
    r"\b(?:ул|улица|пр|просп|проспект|пер|переулок|наб|набережная|"
    r"ш|шоссе|пл|площадь|б-р|бульвар|проезд|туп|тупик|мкр|микрорайон)\b",
    re.IGNORECASE,
)

# These parts should not hide the house in the previous comma-separated part.
_APARTMENT_RE = re.compile(
    r"^(?:кв|квартира|оф|офис|пом|помещение|этаж|эт)\b",
    re.IGNORECASE,
)


def has_house_number(address: Optional[str]) -> bool:
    """Return True when an address contains a house/building number.

    Draft saving stays permissive — an incomplete address can be stored and
    refined later. Only the activation checklist (and activation itself) calls
    this helper, so the green tick has the same meaning as the backend gate.
    """
    if not address or not address.strip():
        return False

    normalized = " ".join(address.split())
    if _HOUSE_MARKER_RE.search(normalized):
        return True

    parts = [part.strip() for part in re.split(r"[,;]", normalized) if part.strip()]
    if not parts:
        return False

    tail = parts[-1]
    # «…, 5, кв. 3»: the apartment part is not the house — inspect the part
    # before it. A bare «кв. 3» without a house stays incomplete.
    if _APARTMENT_RE.match(tail) and len(parts) > 1:
        tail = parts[-2]

    # The tail may be «ул. Ленина 5» (street + house) or just «5».
    if _STREET_WORD_RE.search(tail) and not _TRAILING_HOUSE_RE.search(tail):
        return False

    return bool(_TRAILING_HOUSE_RE.search(tail))
