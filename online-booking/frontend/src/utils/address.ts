/**
 * Cabinet-address completeness, mirrored by backend
 * `app/services/addresses.py`.
 *
 * The draft can store any address, but the activation checklist needs at
 * least a house number. «Москва, ул. Ленина» is a street, not a workplace;
 * «Москва, ул. Ленина, 5» / «…, д. 5» / «…, 5А» are complete enough.
 */

// JS `\b` is ASCII-only, so Cyrillic word boundaries are written as
// explicit «not a letter» guards (the backend uses Python's Unicode \b).
const HOUSE_MARKER_RE =
  /(?:^|[^a-zа-яё])(?:д|дом|двлд|вл|владение|зд|здание|стр|строение|корп|корпус|к)\.?\s*\d/i;

const TRAILING_HOUSE_RE = /(?:^|[\s,])(\d+[a-zа-яё]?(?:\s*[/-]\s*\d+[a-zа-яё]?)?)\s*$/i;

const STREET_WORD_RE =
  /(?:^|[^a-zа-яё])(?:ул|улица|пр|просп|проспект|пер|переулок|наб|набережная|ш|шоссе|пл|площадь|б-р|бульвар|проезд|туп|тупик|мкр|микрорайон)(?=$|[^a-zа-яё])/i;

const APARTMENT_RE = /^(?:кв|квартира|оф|офис|пом|помещение|этаж|эт)(?=$|[^a-zа-яё])/i;

export function hasHouseNumber(address: string | null | undefined): boolean {
  if (!address || !address.trim()) return false;

  const normalized = address.replace(/\s+/g, ' ').trim();
  if (HOUSE_MARKER_RE.test(normalized)) return true;

  const parts = normalized
    .split(/[,;]/)
    .map((part) => part.trim())
    .filter(Boolean);
  if (parts.length === 0) return false;

  let tail = parts[parts.length - 1];
  // «…, 5, кв. 3»: inspect the part before the apartment.
  if (APARTMENT_RE.test(tail) && parts.length > 1) {
    tail = parts[parts.length - 2];
  }

  if (STREET_WORD_RE.test(tail) && !TRAILING_HOUSE_RE.test(tail)) {
    return false;
  }

  return TRAILING_HOUSE_RE.test(tail);
}
