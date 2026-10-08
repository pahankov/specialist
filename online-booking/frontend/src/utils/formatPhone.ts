import { parsePhoneNumberFromString, CountryCode } from 'libphonenumber-js'

/** Format phone number using libphonenumber-js.
 * 
 * Supports all countries with proper formatting, validation, and E.164 output.
 * Defaults to Russia (+7) if no country code specified.
 * 
 * @param value - Raw phone input (digits, +, spaces, dashes)
 * @param defaultCountry - ISO 3166-1 alpha-2 country code (default: 'RU')
 * @returns Formatted phone number in national format
 * 
 * Examples:
 *   formatPhone('9991234567', 'RU') → '+7 (999) 123-45-67'
 *   formatPhone('2125551234', 'US') → '(212) 555-1234'
 *   formatPhone('1712345678', 'DE') → '+49 171 2345678'
 */

export const PHONE_MAX_DIGITS = 15 // E.164 max length

export function formatPhone(value: string, defaultCountry: CountryCode = 'RU'): string {
  if (!value) return ''

  // Cap digit runs (E.164 max): typing must never grow the field unbounded
  const digitsOnly = value.replace(/\D/g, '')
  if (digitsOnly.length > PHONE_MAX_DIGITS) {
    const plus = value.trimStart().startsWith('+') ? '+' : ''
    value = plus + digitsOnly.slice(0, PHONE_MAX_DIGITS)
  }

  const phone = parsePhoneNumberFromString(value, defaultCountry)
  if (!phone || !phone.isValid()) {
    // If invalid, try to format what we can
    const digits = value.replace(/\D/g, '')
    if (digits.length === 0) return ''
    // Fallback: try to format as-is
    return value
  }

  return phone.formatNational()
}

/** Validate phone number for a specific country */
export function validatePhone(value: string, defaultCountry: CountryCode = 'RU'): boolean {
  const phone = parsePhoneNumberFromString(value, defaultCountry)
  return phone?.isValid() ?? false
}

/** Get E.164 format (+79991234567) */
export function formatPhoneE164(value: string, defaultCountry: CountryCode = 'RU'): string {
  const phone = parsePhoneNumberFromString(value, defaultCountry)
  if (!phone) return value
  // Build E.164 manually: +{countryCode}{nationalNumber}
  const countryCode = phone.country || defaultCountry
  const callingCode = countryCode === 'RU' ? '7' : countryCode === 'US' ? '1' : countryCode === 'DE' ? '49' : '1'
  return `+${callingCode}${phone.number.replace(/\D/g, '')}`
}

/** Get country code from phone number */
export function getPhoneCountry(value: string): CountryCode | undefined {
  const phone = parsePhoneNumberFromString(value)
  return phone?.country
}
