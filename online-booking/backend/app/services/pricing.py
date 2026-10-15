"""Single price math: percentage discounts (0-90%)."""

MAX_DISCOUNT = 90


def clamp_discount(pct) -> int:
    try:
        v = int(pct or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, min(MAX_DISCOUNT, v))


def apply_discount(price, pct) -> float:
    """Full price minus pct% (rounded to kopecks). None-safe."""
    try:
        base = float(price or 0)
    except (TypeError, ValueError):
        base = 0.0
    d = clamp_discount(pct)
    return round(base * (100 - d) / 100, 2)
