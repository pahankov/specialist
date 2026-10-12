/** Name casing: first letter of each word upper, rest untouched.
 * "иван" -> "Иван", "анна-мария" -> "Анна-Мария". Applied on input so the
 * user sees the normalized value immediately (Russian + Latin). */
export function capitalizeWords(value: string): string {
  return value.replace(/(^|[\s\-‐‑‑‒–—]+)([a-zа-яё])/giu, (_m, sep: string, ch: string) => {
    // Keep only the last separator char class simple: sep is preserved as-is.
    return `${sep}${ch.toUpperCase()}`;
  });
}

/** Split a stored full name ("Иван Петров") into [first, rest]. */
export function splitFullName(full: string): [string, string] {
  const parts = full.trim().split(/\s+/);
  if (parts.length <= 1) return [full.trim(), ''];
  return [parts[0], parts.slice(1).join(' ')];
}
