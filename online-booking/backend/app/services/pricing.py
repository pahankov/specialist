"""Single price math: percentage discounts (0-90%), optionally time-boxed."""

MAX_DISCOUNT = 90


def clamp_discount(pct) -> int:
    try:
        v = int(pct or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, min(MAX_DISCOUNT, v))


def discount_active(until, now=None) -> bool:
    """A discount with `until` lives only before that moment (naive UTC)."""
    if until is None:
        return True
    from datetime import datetime

    if now is None:
        from app.utils import utcnow_naive
        now = utcnow_naive()
    try:
        end = until.replace(tzinfo=None) if getattr(until, "tzinfo", None) else until
        now_naive = now.replace(tzinfo=None) if getattr(now, "tzinfo", None) else now
        return now_naive < end if isinstance(end, datetime) else True
    except Exception:
        return True


def apply_discount(price, pct, until=None, fixed=0, now=None) -> float:
    """Full price minus pct%, then minus fixed RUB (floored at zero).

    Rounded to kopecks. None-safe. Both parts are optional and stack.
    """
    try:
        base = float(price or 0)
    except (TypeError, ValueError):
        base = 0.0
    d = clamp_discount(pct) if discount_active(until, now) else 0
    try:
        rub = float(fixed or 0) if discount_active(until, now) else 0.0
    except (TypeError, ValueError):
        rub = 0.0
    return round(max(0.0, base * (100 - d) / 100 - max(0.0, rub)), 2)
