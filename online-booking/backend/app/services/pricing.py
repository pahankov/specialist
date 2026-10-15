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


def apply_discount(price, pct, until=None, now=None) -> float:
    """Full price minus pct% (rounded to kopecks). None-safe."""
    try:
        base = float(price or 0)
    except (TypeError, ValueError):
        base = 0.0
    d = clamp_discount(pct) if discount_active(until, now) else 0
    return round(base * (100 - d) / 100, 2)
