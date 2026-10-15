"""City duplicates: DaData variants of one physical city live as separate rows
('Краснодар', 'Россия, г Краснодар', ...). Matching must use the whole
family, not one id — otherwise masters vanish when the client picked
another spelling of the same city.
"""
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.city import City

# Tokens that carry no city identity (country, locality type markers).
JUNK = {
    "россия", "рф", "russia",
    "г", "гор", "город", "д", "дом", "ул", "улица", "пр", "пркт",
    "проспект", "пер", "переулок", "бул", "бульвар", "ш", "шоссе",
    "наб", "набережная", "пл", "площадь", "мкр", "микрорайон",
    "кв", "квартира", "стр", "строение", "корп", "корпус", "лит",
    "литера", "пом", "помещение", "оф", "офис", "эт", "этаж",
}


def city_key(name: str | None) -> str:
    """Normalized identity key: 'Россия, г Краснодар' -> 'краснодар'."""
    if not name:
        return ""
    text = name.lower().replace("ё", "е")
    # Frequent hyphenated abbreviations first (regex would shred them).
    text = re.sub(r"\bпр-кт\b", "проспект", text)
    text = re.sub(r"\bг\b\.?", "", text)
    tokens = re.findall(r"[а-яa-z0-9]+", text)
    kept = [t for t in tokens
            if t not in JUNK and len(t) > 1 and not t.isdigit()]
    return " ".join(kept)


def same_city(a: str, b: str) -> bool:
    """Equal keys, or one extends the other ('краснодар' vs street variant)."""
    if not a or not b or a == b:
        return a == b and bool(a)
    short, long = (a, b) if len(a) < len(b) else (b, a)
    return long.startswith(short + " ")


async def city_family_ids(db: AsyncSession, city_id: int) -> list[int]:
    """Ids of all city rows that are the same physical city (incl. itself)."""
    rows = (await db.execute(select(City.id, City.name_ru))).all()
    anchor = ""
    for cid, cname in rows:
        if cid == city_id:
            anchor = city_key(cname)
            break
    if not anchor:
        return [city_id]
    return [cid for cid, cname in rows if same_city(anchor, city_key(cname))]
