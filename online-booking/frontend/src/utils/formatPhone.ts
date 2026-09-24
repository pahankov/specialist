/** Format phone number for display.

User types 10 digits (e.g. 9991234567) and gets: +7 (999) 123-45-67
The +7 prefix is auto-added and does NOT count toward the 10-digit limit.
*/

export const PHONE_MAX_DIGITS = 10

export function formatPhone(value: string): string {
  // Remove all non-digits, strip ONE leading 7 (from +7 prefix)
  const digits = value.replace(/\D/g, '')
  const cleaned = (digits.startsWith('7') ? digits.slice(1) : digits).slice(0, PHONE_MAX_DIGITS)
  if (cleaned.length === 0) return ''
  
  if (cleaned.length <= 3) {
    return `+7 (${cleaned}`
  }
  if (cleaned.length <= 6) {
    return `+7 (${cleaned.slice(0, 3)}) ${cleaned.slice(3)}`
  }
  if (cleaned.length <= 8) {
    return `+7 (${cleaned.slice(0, 3)}) ${cleaned.slice(3, 6)}-${cleaned.slice(6)}`
  }
  return `+7 (${cleaned.slice(0, 3)}) ${cleaned.slice(3, 6)}-${cleaned.slice(6, 8)}-${cleaned.slice(8, 10)}`
}
